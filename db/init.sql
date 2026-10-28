-- ============================================================
-- TracePulse: High-Throughput Synthetic API & Health Monitoring Engine
-- Production MySQL 8.0 Database Initialization Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS `tracepulse` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `tracepulse`;

-- 1. Monitors Table: Endpoints configuration
CREATE TABLE IF NOT EXISTS `monitors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(128) NOT NULL,
    `target_url` VARCHAR(2048) NOT NULL,
    `http_method` VARCHAR(10) NOT NULL DEFAULT 'GET',
    `headers_json` JSON NULL,
    `body_payload` TEXT NULL,
    `check_interval_sec` INT NOT NULL DEFAULT 10,
    `timeout_ms` INT NOT NULL DEFAULT 5000,
    `expected_status` INT NOT NULL DEFAULT 200,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX `idx_monitors_active` (`is_active`, `check_interval_sec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Check Runs Table: High-throughput microsecond-precision time-series
CREATE TABLE IF NOT EXISTS `check_runs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `monitor_id` INT NOT NULL,
    `status_code` INT NOT NULL,
    `is_success` BOOLEAN NOT NULL,
    `dns_lookup_us` BIGINT NOT NULL DEFAULT 0,
    `tcp_connect_us` BIGINT NOT NULL DEFAULT 0,
    `tls_handshake_us` BIGINT NOT NULL DEFAULT 0,
    `ttfb_us` BIGINT NOT NULL DEFAULT 0,
    `total_duration_us` BIGINT NOT NULL DEFAULT 0,
    `response_bytes` BIGINT NOT NULL DEFAULT 0,
    `error_message` VARCHAR(1024) NULL,
    `checked_at` TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT `fk_check_runs_monitor` FOREIGN KEY (`monitor_id`) REFERENCES `monitors` (`id`) ON DELETE CASCADE,
    INDEX `idx_check_runs_monitor_time` (`monitor_id`, `checked_at` DESC),
    INDEX `idx_check_runs_time` (`checked_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Alert Rules Table: Threshold & incident triggers
CREATE TABLE IF NOT EXISTS `alert_rules` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `monitor_id` INT NOT NULL,
    `rule_type` ENUM('CONSECUTIVE_FAILURES', 'LATENCY_THRESHOLD', 'STATUS_CODE_MISMATCH') NOT NULL,
    `threshold_value` DOUBLE NOT NULL,
    `consecutive_count` INT NOT NULL DEFAULT 1,
    `webhook_url` VARCHAR(2048) NOT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT `fk_alert_rules_monitor` FOREIGN KEY (`monitor_id`) REFERENCES `monitors` (`id`) ON DELETE CASCADE,
    INDEX `idx_alert_rules_monitor` (`monitor_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Alert Incidents Table: Outage tracking and resolution states
CREATE TABLE IF NOT EXISTS `alert_incidents` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `monitor_id` INT NOT NULL,
    `alert_rule_id` INT NULL,
    `status` ENUM('OPEN', 'RESOLVED') NOT NULL DEFAULT 'OPEN',
    `triggered_at` TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `resolved_at` TIMESTAMP(6) NULL,
    `trigger_reason` VARCHAR(1024) NOT NULL,
    CONSTRAINT `fk_alert_incidents_monitor` FOREIGN KEY (`monitor_id`) REFERENCES `monitors` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_alert_incidents_rule` FOREIGN KEY (`alert_rule_id`) REFERENCES `alert_rules` (`id`) ON DELETE SET NULL,
    INDEX `idx_incidents_monitor_status` (`monitor_id`, `status`),
    INDEX `idx_incidents_time` (`triggered_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Initial Seed Targets for synthetic monitoring
INSERT INTO `monitors` (`name`, `target_url`, `http_method`, `check_interval_sec`, `timeout_ms`, `expected_status`)
VALUES 
    ('Cloudflare DNS API', 'https://1.1.1.1/cdn-cgi/trace', 'GET', 5, 3000, 200),
    ('Google Public DNS', 'https://dns.google/resolve?name=example.com', 'GET', 5, 3000, 200),
    ('HTTPBin Status Check', 'https://httpbin.org/status/200', 'GET', 10, 5000, 200)
ON DUPLICATE KEY UPDATE `id`=`id`;
