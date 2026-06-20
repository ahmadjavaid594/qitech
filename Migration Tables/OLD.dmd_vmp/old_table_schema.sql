-- qitech.dmd_vmps definition

CREATE TABLE `dmd_vmps` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vtmid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `abbrev_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `basis_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pres_stat_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `df_ind` tinyint(1) DEFAULT NULL,
  `udfs` decimal(10,2) DEFAULT NULL,
  `udfs_uomcd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `unit_dose_uomcd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_vmps_vpid_unique` (`vpid`)
) ENGINE=InnoDB AUTO_INCREMENT=24346 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;