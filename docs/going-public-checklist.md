# 转公开前 checklist

规则: 任何内容公开前必扫个人信息。全部勾完才允许 `gh repo edit --visibility public`。

- [ ] 全历史个人信息扫描: `git log -p --all` 里无手机号/邮箱/证件号/住址;
      本机绝对路径(形如 C:/Users/<用户名>、中文桌面目录)只允许出现在 docs/ 的历史记录性文档里,
      逐处确认可接受或改写
- [ ] 确认 data/、models/、config.yaml 从未进过历史:
      `git log --all --name-only --pretty=format: | sort -u` 无这三类路径
- [ ] README/docs 里的截图与 demo 素材不含真实生活片段(用 lavfi 合成视频演示)
- [ ] LICENSE 年份与署名正确
- [ ] GitHub repo description 与 topics 已写好(作品集口径, 对齐 ai-job-hunt-pipeline 风格)
- [ ] 执行: `gh repo edit haiiibin/vlog-pipeline --visibility public`
