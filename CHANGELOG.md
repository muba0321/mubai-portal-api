# Changelog

All notable changes to SRE Portal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.5] - 2026-05-19

### Fixed
- 配合前端 proxy rewrite 修复，API 路径统一（无变更）

### Added
- 版本文件 VERSION 更新为 1.0.5

## [1.0.0] - 2026-05-13

### Added
- 前端：Vue3 + Element Plus 管理后台，包含首页 Dashboard、CMDB 虚拟机管理
- 后端：Flask REST API，JWT 认证、用户管理、CMDB 管理、Dashboard 接口
- 数据库：MySQL 表结构（用户、菜单、虚拟机、常用链接、访问记录、系统监控）
- 前端：Vite 代理转发，自动登录（admin/admin123）
- 前端：路由守卫、动态路由、布局系统（侧边栏+顶部导航+TagsView）
- 后端：Flask-JWT-Extended 认证、刷新 token
- 后端：Flask-Migrate 数据库迁移支持
