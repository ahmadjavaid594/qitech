-- qitech.user_job_assigns definition

CREATE TABLE `user_job_assigns` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `location_id` int unsigned DEFAULT NULL,
  `head_office_id` int unsigned DEFAULT NULL,
  `job_id` bigint unsigned NOT NULL,
  `subtypes` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `regulatory_body_id` bigint unsigned DEFAULT NULL,
  `reg_no` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `also_is` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_job_assigns_user_id_foreign` (`user_id`),
  KEY `user_job_assigns_location_id_foreign` (`location_id`),
  KEY `user_job_assigns_head_office_id_foreign` (`head_office_id`),
  KEY `user_job_assigns_job_id_foreign` (`job_id`),
  KEY `user_job_assigns_regulatory_body_id_foreign` (`regulatory_body_id`),
  CONSTRAINT `user_job_assigns_head_office_id_foreign` FOREIGN KEY (`head_office_id`) REFERENCES `head_offices` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_job_assigns_job_id_foreign` FOREIGN KEY (`job_id`) REFERENCES `user_jobs` (`id`),
  CONSTRAINT `user_job_assigns_location_id_foreign` FOREIGN KEY (`location_id`) REFERENCES `locations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_job_assigns_regulatory_body_id_foreign` FOREIGN KEY (`regulatory_body_id`) REFERENCES `job_regulatory_body` (`id`),
  CONSTRAINT `user_job_assigns_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7154 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;