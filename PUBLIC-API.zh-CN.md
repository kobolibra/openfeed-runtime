# 精确的公开JSON接口规则

JSON接口可通过管理API或规则导入设置。现有表单POST继续使用request_data；需要application/json请求体时使用request_json，数字、数组、布尔和null会保留类型。预览、保存刷新、诊断共用请求构造。

```json
{
  "mode": "json",
  "fetch_mode": "http",
  "request_method": "POST",
  "request_json": {"q": "China", "from": 1, "size": 6},
  "item_selector": "data",
  "json_contract": {"success": true, "parameters.q": "China"},
  "fields": {"title": "headline", "link": "url", "date": "date", "summary": "teasertext"}
}
```

示例只展示字段结构，不代表任何站点已验收。应从官网真实请求和响应确认路径与筛选参数。服务器可能忽略某些字段：例如本次Woodmac接口保留China查询，却用配置覆盖Opinion筛选；设置相应json_contract后会拒绝这类响应，保留已有RSS。

官方空列表需要同时设置item_selector、与其相同的empty_json_path及非空json_contract，例如{"statusCode":200}。只有正确路径的真正空数组才算官方空列表。字段缺失、错误状态、无效条目数组均不能当作空。空RSS不代表抓到了新文章或岗位。

请求体限制：顶层20键、总计500节点、最多4层、单数组50项、单字符串2000字符、UTF-8总计16KB；不允许NaN、Infinity或混用表单。网络仍使用公网验证、TLS和有界读取。JSON POST的307/308跨源重定向被拒绝；303转GET不带请求体。

浏览器抓取保留真实HTTP状态和Retry-After，经IPC严格校验后进入现有429/503调度退避。此改进不代表能够绕过登录、会员或访问验证。

原网页与取数接口可以分离：订阅source_url保留官网栏目地址，recipe.fetch_url指定经验证的公开数据接口。RSS频道链接、OPML页面链接及管理页使用原网页；预览、保存刷新、诊断使用同一取数接口。fetch_url仍必须满足公网URL限制。同域节流按实际请求目标计算。此能力不能把一个403接口变成可访问接口。

## Web Component 的 JSON 属性

CSS 字段可读取组件属性中的 JSON，例如 `:scope@link::json.href`、`:scope@teasermeta::json.date`。标题可显式配置最多三个回退字段，例如 `:scope@teaserheader::json.headline ?? :scope@articletitle`。只解析 JSON，不执行组件代码；单属性上限 100000 字符，错误 JSON 会使该轮失败并保留已有 RSS。Julius Baer Insights 的文章卡片与置顶文章使用此能力。
