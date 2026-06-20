-- qitech.dmd_ampps definition

CREATE TABLE `dmd_ampps` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `appid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `apid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vppid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `legal_catcd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subp` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `disccd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `discdt` date DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dmd_ampps_appid_unique` (`appid`),
  KEY `dmd_ampps_apid_foreign` (`apid`),
  KEY `dmd_ampps_vppid_foreign` (`vppid`),
  CONSTRAINT `dmd_ampps_apid_foreign` FOREIGN KEY (`apid`) REFERENCES `dmd_amps` (`apid`) ON DELETE CASCADE,
  CONSTRAINT `dmd_ampps_vppid_foreign` FOREIGN KEY (`vppid`) REFERENCES `dmd_vmpps` (`vppid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=183981 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;