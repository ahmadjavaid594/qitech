-- qitech.dmd_vmpps definition

CREATE TABLE `dmd_vmpps` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vppid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `qtyval` decimal(8,3) DEFAULT NULL,
  `qty_uomcd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_vmpps_vppid_unique` (`vppid`),
  KEY `dmd_vmpps_vpid_foreign` (`vpid`),
  KEY `dmd_vmpps_qty_uomcd_foreign` (`qty_uomcd`),
  CONSTRAINT `dmd_vmpps_qty_uomcd_foreign` FOREIGN KEY (`qty_uomcd`) REFERENCES `dmd_unit_of_measures` (`cd`) ON DELETE CASCADE,
  CONSTRAINT `dmd_vmpps_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=36873 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;