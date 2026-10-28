#include <iostream>
#include <chrono>
#include <thread>
#include <csignal>
#include <atomic>
#include <map>
#include <cstdlib>

#include "curl_client.hpp"
#include "thread_pool.hpp"
#include "batch_queue.hpp"
#include "config_manager.hpp"

static std::atomic<bool> g_running{true};

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\n[Daemon] Received shutdown signal. Gracefully stopping..." << std::endl;
        g_running = false;
    }
}

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::string control_plane_url = "http://127.0.0.1:8000";
    if (const char* env_url = std::getenv("CONTROL_PLANE_URL")) {
        control_plane_url = env_url;
    }
    if (argc > 1) {
        control_plane_url = argv[1];
    }

    std::string ingest_key = "tp-internal-probe-secret";
    if (const char* env_key = std::getenv("INTERNAL_INGEST_KEY")) {
        ingest_key = env_key;
    }

    std::cout << "========================================================\n"
              << " TracePulse High-Throughput C++ Probe Engine v1.0.0\n"
              << " Control Plane: " << control_plane_url << "\n"
              << " Threads: " << (std::thread::hardware_concurrency() * 2) << "\n"
              << "========================================================" << std::endl;

    tracepulse::CurlClient::global_init();

    tracepulse::ThreadPool pool(std::thread::hardware_concurrency() * 2);
    tracepulse::BatchQueue batch_queue;
    tracepulse::ConfigManager config_mgr(control_plane_url);

    // Dedicated background flusher thread
    std::thread flusher([&]() {
        while (g_running) {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            auto batch = batch_queue.drain_batch(50);
            if (!batch.empty()) {
                std::string payload = tracepulse::BatchQueue::serialize_batch_json(batch);
                bool ok = config_mgr.post_batch_metrics(payload, ingest_key);
                if (ok) {
                    std::cout << "[Flusher] Successfully flushed " << batch.size() << " probe metrics." << std::endl;
                } else {
                    std::cerr << "[Flusher] Warning: Failed to deliver batch to control plane." << std::endl;
                }
            }
        }
    });

    std::map<int, std::chrono::steady_clock::time_point> next_check_time;
    auto last_target_refresh = std::chrono::steady_clock::now() - std::chrono::seconds(60);
    std::vector<tracepulse::ProbeTarget> targets;

    while (g_running) {
        auto now = std::chrono::steady_clock::now();

        // Refresh targets from control plane every 10 seconds
        if (now - last_target_refresh > std::chrono::seconds(10)) {
            targets = config_mgr.fetch_active_targets();
            last_target_refresh = now;
            std::cout << "[Scheduler] Active monitored targets: " << targets.size() << std::endl;
        }

        // Schedule due targets
        for (const auto& target : targets) {
            if (next_check_time.find(target.id) == next_check_time.end() || now >= next_check_time[target.id]) {
                next_check_time[target.id] = now + std::chrono::seconds(target.interval_sec);

                // Dispatch probe task to worker pool
                pool.enqueue([target, &batch_queue]() {
                    auto metric = tracepulse::CurlClient::execute_probe(target);
                    std::cout << "[Probe] ID " << target.id << " -> " << target.url 
                              << " | Status: " << metric.status_code 
                              << " | Total: " << (metric.total_duration_us / 1000.0) << "ms"
                              << " (TTFB: " << (metric.ttfb_us / 1000.0) << "ms)" << std::endl;
                    batch_queue.push(metric);
                });
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    pool.stop();
    if (flusher.joinable()) {
        flusher.join();
    }

    // Flush any remaining metrics
    auto remaining = batch_queue.drain_batch(100);
    if (!remaining.empty()) {
        std::string payload = tracepulse::BatchQueue::serialize_batch_json(remaining);
        config_mgr.post_batch_metrics(payload, ingest_key);
    }

    tracepulse::CurlClient::global_cleanup();
    std::cout << "[Daemon] Shutdown complete. All worker threads joined." << std::endl;
    return 0;
}
