#pragma once

#include <vector>
#include <mutex>
#include <string>
#include "curl_client.hpp"

namespace tracepulse {

class BatchQueue {
public:
    explicit BatchQueue(size_t max_capacity = 10000);

    void push(const ProbeMetric& metric);
    std::vector<ProbeMetric> drain_batch(size_t max_batch_size = 50);
    size_t size() const;

    static std::string serialize_batch_json(const std::vector<ProbeMetric>& batch);

private:
    std::vector<ProbeMetric> buffer_;
    mutable std::mutex buffer_mutex_;
    size_t max_capacity_;
};

} // namespace tracepulse
