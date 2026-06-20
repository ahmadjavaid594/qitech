-- qitech.dmd_ingredients definition

CREATE TABLE `dmd_ingredients` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `isid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `isid_date` date DEFAULT NULL,
  `isid_prev` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_ingredients_isid_unique` (`isid`)
) ENGINE=InnoDB AUTO_INCREMENT=4483 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;