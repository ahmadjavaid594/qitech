-- qitech.dmd_suppliers definition

CREATE TABLE `dmd_suppliers` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `desc` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cd_prev` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cd_date` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_suppliers_cd_unique` (`cd`)
) ENGINE=InnoDB AUTO_INCREMENT=2369 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;