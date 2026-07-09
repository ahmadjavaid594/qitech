-- qitech.head_office_orginisation_levels definition

CREATE TABLE `head_office_orginisation_levels` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `head_office_id` int unsigned NOT NULL,
  `level_number` int NOT NULL,
  `level_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `head_office_orginisation_levels_head_office_id_foreign` (`head_office_id`),
  CONSTRAINT `head_office_orginisation_levels_head_office_id_foreign` FOREIGN KEY (`head_office_id`) REFERENCES `head_offices` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=62 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;