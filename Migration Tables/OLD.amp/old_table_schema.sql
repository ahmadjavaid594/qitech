-- qitech.amp definition

CREATE TABLE `amp` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `VPID` bigint NOT NULL,
  `APID` bigint DEFAULT NULL,
  `NM` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  `DESC` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=149893 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;