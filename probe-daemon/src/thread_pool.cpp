#include "thread_pool.hpp"

namespace tracepulse {

ThreadPool::ThreadPool(size_t num_threads) {
    if (num_threads == 0) num_threads = 4;
    workers_.reserve(num_threads);

    for (size_t i = 0; i < num_threads; ++i) {
        workers_.emplace_back([this]() {
            while (true) {
                std::function<void()> task;
                {
                    std::unique_lock<std::mutex> lock(this->queue_mutex_);
                    this->cv_.wait(lock, [this]() {
                        return this->is_stopped_ || !this->task_queue_.empty();
                    });

                    if (this->is_stopped_ && this->task_queue_.empty()) {
                        return;
                    }

                    task = std::move(this->task_queue_.front());
                    this->task_queue_.pop();
                }

                if (task) {
                    task();
                }
            }
        });
    }
}

ThreadPool::~ThreadPool() {
    stop();
}

void ThreadPool::enqueue(std::function<void()> task) {
    {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        if (is_stopped_) return;
        task_queue_.push(std::move(task));
    }
    cv_.notify_one();
}

void ThreadPool::stop() {
    bool expected = false;
    if (is_stopped_.compare_exchange_strong(expected, true)) {
        cv_.notify_all();
        for (std::thread& worker : workers_) {
            if (worker.joinable()) {
                worker.join();
            }
        }
    }
}

size_t ThreadPool::active_worker_count() const {
    return workers_.size();
}

} // namespace tracepulse
