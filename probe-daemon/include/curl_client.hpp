#pragma once

#include <string>
#include <cstdint>
#include <optional>
#include <curl/curl.h>

namespace tracepulse {

struct ProbeTarget {
    int id{0};
    std::string name;
    std::string url;
    std::string method{"GET"};
    std::string headers_json;
    std::string body;
    int interval_sec{10};
    int timeout_ms{5000};
    int expected_status{200};
};

struct ProbeMetric {
    int monitor_id{0};
    int status_code{0};
    bool is_success{false};
    uint64_t dns_lookup_us{0};
    uint64_t tcp_connect_us{0};
    uint64_t tls_handshake_us{0};
    uint64_t ttfb_us{0};
    uint64_t total_duration_us{0};
    uint64_t response_bytes{0};
    std::string error_message;
    std::string timestamp_iso;

    std::string to_json() const;
};

class CurlClient {
public:
    static void global_init();
    static void global_cleanup();

    static ProbeMetric execute_probe(const ProbeTarget& target);
};

} // namespace tracepulse
