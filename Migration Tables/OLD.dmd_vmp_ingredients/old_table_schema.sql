-- qitech.dmd_vmp_ingredients definition

CREATE TABLE `dmd_vmp_ingredients` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `isid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `basis_strength_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `strength_value` decimal(12,4) DEFAULT NULL,
  `strength_uomcd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dmd_vmp_ingredients_vpid_foreign` (`vpid`),
  KEY `dmd_vmp_ingredients_isid_foreign` (`isid`),
  CONSTRAINT `dmd_vmp_ingredients_isid_foreign` FOREIGN KEY (`isid`) REFERENCES `dmd_ingredients` (`isid`) ON DELETE CASCADE,
  CONSTRAINT `dmd_vmp_ingredients_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=26683 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;