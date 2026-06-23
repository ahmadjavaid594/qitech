-- qitech.head_office_user_holidays definition

CREATE TABLE `head_office_user_holidays` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `head_office_user_id` bigint unsigned NOT NULL,
  `away_from` date NOT NULL,
  `return_on` date NOT NULL,
  `total_days` int NOT NULL,
  `type` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `linked_api_holiday_id` bigint unsigned DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `head_office_user_holidays_head_office_user_id_foreign` (`head_office_user_id`),
  KEY `head_office_user_holidays_linked_api_holiday_id_foreign` (`linked_api_holiday_id`),
  CONSTRAINT `head_office_user_holidays_head_office_user_id_foreign` FOREIGN KEY (`head_office_user_id`) REFERENCES `head_office_users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `head_office_user_holidays_linked_api_holiday_id_foreign` FOREIGN KEY (`linked_api_holiday_id`) REFERENCES `head_office_users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;