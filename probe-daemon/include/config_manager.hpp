#pragma once

#include <vector>
#include <string>
#include "curl_client.hpp"

namespace tracepulse {

class ConfigManager {
public:
    explicit ConfigManager(std::string control_plane_url);

    std::vector<ProbeTarget> fetch_active_targets();
    bool post_batch_metrics(const std::string& serialized_json, const std::string& ingest_key);

private:
    std::string control_plane_url_;
    static size_t write_callback(void* contents, size_t size, size_t nmemb, void* userp);
};

} // namespace tracepulse
