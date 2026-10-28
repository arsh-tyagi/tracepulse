#include "curl_client.hpp"
#include <sstream>
#include <chrono>
#include <iomanip>
#include <iostream>

namespace tracepulse {

static size_t discard_write_callback(void* /*contents*/, size_t size, size_t nmemb, void* /*userp*/) {
    return size * nmemb;
}

void CurlClient::global_init() {
    curl_global_init(CURL_GLOBAL_ALL);
}

void CurlClient::global_cleanup() {
    curl_global_cleanup();
}

std::string ProbeMetric::to_json() const {
    std::ostringstream ss;
    ss << "{"
       << "\"monitor_id\":" << monitor_id << ","
       << "\"status_code\":" << status_code << ","
       << "\"is_success\":" << (is_success ? "true" : "false") << ","
       << "\"dns_lookup_us\":" << dns_lookup_us << ","
       << "\"tcp_connect_us\":" << tcp_connect_us << ","
       << "\"tls_handshake_us\":" << tls_handshake_us << ","
       << "\"ttfb_us\":" << ttfb_us << ","
       << "\"total_duration_us\":" << total_duration_us << ","
       << "\"response_bytes\":" << response_bytes << ",";
    if (error_message.empty()) {
        ss << "\"error_message\":null";
    } else {
        // Simple escape for error message
        ss << "\"error_message\":\"";
        for (char c : error_message) {
            if (c == '"' || c == '\\') ss << '\\';
            if (c >= 32 && c <= 126) ss << c;
        }
        ss << "\"";
    }
    ss << "}";
    return ss.str();
}

ProbeMetric CurlClient::execute_probe(const ProbeTarget& target) {
    ProbeMetric metric;
    metric.monitor_id = target.id;

    CURL* curl = curl_easy_init();
    if (!curl) {
        metric.status_code = 0;
        metric.is_success = false;
        metric.error_message = "Failed to initialize libcurl handle";
        return metric;
    }

    // Set target options with safety bounds
    long timeout = std::max(500L, static_cast<long>(target.timeout_ms));
    curl_easy_setopt(curl, CURLOPT_URL, target.url.c_str());
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L); // Mandatory for multi-threading
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, timeout);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, std::max(200L, timeout / 2));
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 5L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, discard_write_callback);

    if (target.method == "HEAD") {
        curl_easy_setopt(curl, CURLOPT_NOBODY, 1L);
    } else if (target.method == "POST") {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        if (!target.body.empty()) {
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, target.body.c_str());
        }
    }

    // Execute synchronous probe
    CURLcode res = curl_easy_perform(curl);

    if (res == CURLE_OK) {
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        metric.status_code = static_cast<int>(http_code);
        metric.is_success = (metric.status_code == target.expected_status);

        curl_off_t namelookup = 0, connect = 0, appconnect = 0, starttransfer = 0, total = 0, size_dl = 0;
        curl_easy_getinfo(curl, CURLINFO_NAMELOOKUP_TIME_T, &namelookup);
        curl_easy_getinfo(curl, CURLINFO_CONNECT_TIME_T, &connect);
        curl_easy_getinfo(curl, CURLINFO_APPCONNECT_TIME_T, &appconnect);
        curl_easy_getinfo(curl, CURLINFO_STARTTRANSFER_TIME_T, &starttransfer);
        curl_easy_getinfo(curl, CURLINFO_TOTAL_TIME_T, &total);
        curl_easy_getinfo(curl, CURLINFO_SIZE_DOWNLOAD_T, &size_dl);

        metric.dns_lookup_us = static_cast<uint64_t>(namelookup);
        metric.tcp_connect_us = (connect >= namelookup) ? static_cast<uint64_t>(connect - namelookup) : 0;
        metric.tls_handshake_us = (appconnect >= connect) ? static_cast<uint64_t>(appconnect - connect) : 0;
        
        uint64_t handshake_baseline = (appconnect > 0) ? appconnect : connect;
        metric.ttfb_us = (starttransfer >= handshake_baseline) ? static_cast<uint64_t>(starttransfer - handshake_baseline) : 0;
        metric.total_duration_us = static_cast<uint64_t>(total);
        metric.response_bytes = static_cast<uint64_t>(size_dl);

        if (!metric.is_success) {
            std::ostringstream err;
            err << "HTTP status " << metric.status_code << " != expected " << target.expected_status;
            metric.error_message = err.str();
        }
    } else {
        metric.status_code = 0;
        metric.is_success = false;
        metric.total_duration_us = static_cast<uint64_t>(target.timeout_ms * 1000);
        metric.error_message = curl_easy_strerror(res);
    }

    curl_easy_cleanup(curl);
    return metric;
}

} // namespace tracepulse
