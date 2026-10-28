#include "config_manager.hpp"
#include <iostream>
#include <sstream>
#include <cstring>

namespace tracepulse {

size_t ConfigManager::write_callback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t total_size = size * nmemb;
    std::string* response_str = static_cast<std::string*>(userp);
    response_str->append(static_cast<char*>(contents), total_size);
    return total_size;
}

static int safe_stoi(const std::string& str, int fallback = 0) {
    try {
        return std::stoi(str);
    } catch (...) {
        return fallback;
    }
}

ConfigManager::ConfigManager(std::string control_plane_url)
    : control_plane_url_(std::move(control_plane_url)) {}

std::vector<ProbeTarget> ConfigManager::fetch_active_targets() {
    std::vector<ProbeTarget> targets;
    CURL* curl = curl_easy_init();
    if (!curl) return targets;

    std::string endpoint = control_plane_url_ + "/api/v1/monitors/active/targets";
    std::string response_buffer;

    curl_easy_setopt(curl, CURLOPT_URL, endpoint.c_str());
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 3000L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_buffer);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        std::cerr << "[ConfigManager] Failed to fetch targets: " << curl_easy_strerror(res) << std::endl;
        return targets;
    }

    // Lightweight hardened parsing of the returned JSON targets array
    size_t pos = 0;
    while ((pos = response_buffer.find("\"id\":", pos)) != std::string::npos) {
        ProbeTarget target;
        try {
            // Parse ID
            pos += 5;
            target.id = safe_stoi(response_buffer.substr(pos), 0);

            // Parse Name
            size_t name_pos = response_buffer.find("\"name\":\"", pos);
            if (name_pos != std::string::npos) {
                name_pos += 8;
                size_t name_end = response_buffer.find("\"", name_pos);
                if (name_end != std::string::npos) {
                    target.name = response_buffer.substr(name_pos, name_end - name_pos);
                }
            }

            // Parse URL
            size_t url_pos = response_buffer.find("\"url\":\"", pos);
            if (url_pos != std::string::npos) {
                url_pos += 7;
                size_t url_end = response_buffer.find("\"", url_pos);
                if (url_end != std::string::npos) {
                    target.url = response_buffer.substr(url_pos, url_end - url_pos);
                }
            }

            // Parse Interval
            size_t interval_pos = response_buffer.find("\"interval_sec\":", pos);
            if (interval_pos != std::string::npos) {
                interval_pos += 15;
                target.interval_sec = safe_stoi(response_buffer.substr(interval_pos), 10);
            }

            // Parse Timeout
            size_t timeout_pos = response_buffer.find("\"timeout_ms\":", pos);
            if (timeout_pos != std::string::npos) {
                timeout_pos += 13;
                target.timeout_ms = safe_stoi(response_buffer.substr(timeout_pos), 5000);
            }

            // Parse Expected Status
            size_t status_pos = response_buffer.find("\"expected_status\":", pos);
            if (status_pos != std::string::npos) {
                status_pos += 18;
                target.expected_status = safe_stoi(response_buffer.substr(status_pos), 200);
            }

            if (!target.url.empty() && target.id > 0) {
                targets.push_back(target);
            }
        } catch (...) {
            // Skip malformed record gracefully
        }
    }

    return targets;
}

bool ConfigManager::post_batch_metrics(const std::string& serialized_json, const std::string& ingest_key) {
    CURL* curl = curl_easy_init();
    if (!curl) return false;

    std::string endpoint = control_plane_url_ + "/api/v1/internal/ingest";
    std::string response_buffer;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    if (!ingest_key.empty()) {
        std::string auth_header = "x-probe-key: " + ingest_key;
        headers = curl_slist_append(headers, auth_header.c_str());
    }

    curl_easy_setopt(curl, CURLOPT_URL, endpoint.c_str());
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, serialized_json.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 4000L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_buffer);

    CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    return (res == CURLE_OK && http_code == 201);
}

} // namespace tracepulse
