-- qitech.dmd_amps definition

CREATE TABLE `dmd_amps` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `apid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name_date` date DEFAULT NULL,
  `name_prev` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `supp_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `lic_auth_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `avail_restrict_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_amps_apid_unique` (`apid`),
  KEY `dmd_amps_vpid_foreign` (`vpid`),
  KEY `dmd_amps_supp_cd_foreign` (`supp_cd`),
  CONSTRAINT `dmd_amps_supp_cd_foreign` FOREIGN KEY (`supp_cd`) REFERENCES `dmd_suppliers` (`cd`) ON DELETE CASCADE,
  CONSTRAINT `dmd_amps_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=164582 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;