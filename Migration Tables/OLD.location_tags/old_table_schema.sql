-- qitech.location_tags definition

CREATE TABLE `location_tags` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `head_office_id` int unsigned NOT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `color` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '#000',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `location_id` int unsigned NOT NULL,
  `icon` int NOT NULL DEFAULT '0',
  `icon_color` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '#ffffff',
  `text_color` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '#ffffff',
  PRIMARY KEY (`id`),
  KEY `location_tags_head_office_id_foreign` (`head_office_id`),
  KEY `location_tags_location_id_foreign` (`location_id`),
  CONSTRAINT `location_tags_head_office_id_foreign` FOREIGN KEY (`head_office_id`) REFERENCES `head_offices` (`id`),
  CONSTRAINT `location_tags_location_id_foreign` FOREIGN KEY (`location_id`) REFERENCES `locations` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=74 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;