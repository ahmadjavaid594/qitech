-- qitech.user_jobs definition

CREATE TABLE `user_jobs` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `module` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `job` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `example` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `job_description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `subtype` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `req_reg` tinyint(1) NOT NULL DEFAULT '0',
  `headoffice_id` int unsigned DEFAULT NULL,
  `multiple_subtypes` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `user_jobs_headoffice_id_foreign` (`headoffice_id`),
  CONSTRAINT `user_jobs_headoffice_id_foreign` FOREIGN KEY (`headoffice_id`) REFERENCES `head_offices` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1253 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;