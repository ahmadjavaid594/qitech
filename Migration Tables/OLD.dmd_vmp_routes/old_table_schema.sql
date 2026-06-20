-- qitech.dmd_vmp_routes definition

CREATE TABLE `dmd_vmp_routes` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `route_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dmd_vmp_routes_vpid_foreign` (`vpid`),
  KEY `dmd_vmp_routes_route_cd_foreign` (`route_cd`),
  CONSTRAINT `dmd_vmp_routes_route_cd_foreign` FOREIGN KEY (`route_cd`) REFERENCES `dmd_routes` (`cd`) ON DELETE CASCADE,
  CONSTRAINT `dmd_vmp_routes_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=22557 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;