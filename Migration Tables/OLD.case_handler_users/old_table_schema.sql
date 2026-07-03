-- qitech.case_handler_users definition

CREATE TABLE `case_handler_users` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `head_office_user_id` bigint unsigned NOT NULL,
  `case_id` bigint unsigned NOT NULL,
  `note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `master_stage_handler` tinyint(1) NOT NULL DEFAULT '0',
  `deleted_at` timestamp NULL DEFAULT NULL,
  `is_hidden` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `case_handler_users_head_office_user_id_case_id_unique` (`head_office_user_id`,`case_id`),
  KEY `case_handler_users_case_id_foreign` (`case_id`),
  CONSTRAINT `case_handler_users_case_id_foreign` FOREIGN KEY (`case_id`) REFERENCES `head_office_cases` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `case_handler_users_head_office_user_id_foreign` FOREIGN KEY (`head_office_user_id`) REFERENCES `head_office_users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=24497 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;