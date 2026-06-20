-- qitech.dmd_vmp_control_drug_info definition

CREATE TABLE `dmd_vmp_control_drug_info` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `vpid` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cat_cd` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dmd_vmp_control_drug_info_vpid_foreign` (`vpid`),
  KEY `dmd_vmp_control_drug_info_cat_cd_foreign` (`cat_cd`),
  CONSTRAINT `dmd_vmp_control_drug_info_cat_cd_foreign` FOREIGN KEY (`cat_cd`) REFERENCES `dmd_control_drug_categories` (`cd`) ON DELETE CASCADE,
  CONSTRAINT `dmd_vmp_control_drug_info_vpid_foreign` FOREIGN KEY (`vpid`) REFERENCES `dmd_vmps` (`vpid`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=24346 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;