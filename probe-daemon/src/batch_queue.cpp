#include "batch_queue.hpp"
#include <sstream>

namespace tracepulse {

BatchQueue::BatchQueue(size_t max_capacity) : max_capacity_(max_capacity) {
    buffer_.reserve(max_capacity_);
}

void BatchQueue::push(const ProbeMetric& metric) {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    if (buffer_.size() < max_capacity_) {
        buffer_.push_back(metric);
    }
}

std::vector<ProbeMetric> BatchQueue::drain_batch(size_t max_batch_size) {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    if (buffer_.empty()) {
        return {};
    }

    size_t count = std::min(max_batch_size, buffer_.size());
    std::vector<ProbeMetric> batch(buffer_.begin(), buffer_.begin() + count);
    buffer_.erase(buffer_.begin(), buffer_.begin() + count);
    return batch;
}

size_t BatchQueue::size() const {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    return buffer_.size();
}

std::string BatchQueue::serialize_batch_json(const std::vector<ProbeMetric>& batch) {
    std::ostringstream ss;
    ss << "{\"checks\":[";
    for (size_t i = 0; i < batch.size(); ++i) {
        ss << batch[i].to_json();
        if (i + 1 < batch.size()) {
            ss << ",";
        }
    }
    ss << "]}";
    return ss.str();
}

} // namespace tracepulse
