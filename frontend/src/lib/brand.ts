/**
 * 品牌与站点信息集中配置：所有可变更项都从这里读取，
 * 后续如需支持环境变量/后台配置，替换此文件即可全局生效。
 */
export const APP_NAME = "LinPass SSO";
export const APP_TAGLINE = "一次注册，通行所有授权网站";
export const COPYRIGHT_HOLDER = APP_NAME;
export const DOCUMENT_TITLE = `${APP_NAME} · 统一登录门户`;
export const FAVICON_PATH = "/favicon.svg";

// TODO: 上线前替换为真实备案信息
export const ICP_FILING_TEXT = "京ICP备00000000号-1";
export const ICP_FILING_URL = "https://beian.miit.gov.cn/";
export const ICP_FILING_ICON = "/badges/icp.svg";
export const POLICE_FILING_TEXT = "京公网安备 11000000000000号";
export const POLICE_FILING_URL = "https://beian.mps.gov.cn/";
export const POLICE_FILING_ICON = "/badges/police.svg";

/**
 * 页脚附加链接（帮助中心/隐私政策/服务条款等）。
 * 当前为空数组表示不展示；需要时填入即可：
 * [{ label: "帮助中心", href: "/help" }]
 */
export const FOOTER_LINKS: { label: string; href: string }[] = [];
