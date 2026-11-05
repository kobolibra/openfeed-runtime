/* Basic Chinese/English interface translation; never stores private data. */
(function(){
'use strict';
const zh={
 nav_overview:'概览',nav_feeds:'全部订阅源',nav_activity:'运行记录',nav_new:'新建订阅源',nav_import:'导入与导出',
 tracked:'监控中的信息源',subhead:'查看所有订阅源及其最新运行状态。',recent:'最近活动',recent_sub:'各订阅源的最新抓取记录',
 feed_name:'订阅源名称',interval:'检查频率',source_type:'来源类型',extraction:'内容提取规则',fetch:'抓取引擎',
 content_type:'内容类型',inventory:'职位清单完整性',selector_lang:'选择器语言',global_scope:'Feed43 全局范围（可选）',
 item_container:'重复文章容器',next_page:'下一页 CSS 选择器（可选）',max_pages:'单次最多抓取页数',
 min_items:'单次抓取最少条目数',min_dated:'具有发布日期的最低比例（%）',
 title_sel:'标题选择器',link_sel:'原文链接选择器',date_sel:'日期选择器',summary_sel:'摘要选择器',
 test:'◎ 测试提取',picker:'◈ 可视化选择',diagnose:'⚕ 诊断规则',welcome:'欢迎回来',
 auth_help:'输入此私人实例所配置的管理员访问令牌。',access_token:'访问令牌',unlock:'解锁工作台 →'
};
const en=new Map();
let language='en';
try{language=localStorage.getItem('openfeed-language')==='zh'?'zh':'en'}catch{}
function apply(){
 document.documentElement.lang=language==='zh'?'zh-CN':'en';
 document.querySelectorAll('[data-i18n]').forEach(el=>{
  const key=el.getAttribute('data-i18n');
  if(!en.has(key))en.set(key,el.textContent);
  el.textContent=language==='zh'?(zh[key]||en.get(key)):en.get(key);
 });
 const toggle=document.getElementById('language-toggle');
 if(toggle){toggle.textContent=language==='zh'?'EN':'中文';toggle.setAttribute('aria-label',language==='zh'?'Switch to English':'切换至中文')}
}
function toggle(){language=language==='zh'?'en':'zh';try{localStorage.setItem('openfeed-language',language)}catch{};apply()}
window.OpenFeedI18n={apply,toggle,get language(){return language;}};
})();
