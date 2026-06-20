-- qitech.dmd_vtms definition

CREATE TABLE `dmd_vtms` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vtmid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vtmidprev` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `vtmiddt` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_vtms_vtmid_unique` (`vtmid`)
) ENGINE=InnoDB AUTO_INCREMENT=3217 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;