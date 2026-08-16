/**
 * 品牌与站点信息集中配置：优先从构建期环境变量（VITE_*，见 frontend/.env.example）
 * 读取，未设置时回退到本文件默认值，保证开箱即用。
 *
 * 图标约定：路径默认指向 frontend/public/ 下的静态资源。
 * 后期替换品牌图标时，直接覆盖对应文件，或修改下方变量指向新路径即可。
 */

const env = import.meta.env;

function envString(name: string, fallback: string): string {
  const value = env[name];
  return typeof value === "string" && value.trim() !== ""
    ? value.trim()
    : fallback;
}

export const APP_NAME = envString("VITE_APP_NAME", "Li&Pass");
export const APP_TAGLINE = envString(
  "VITE_APP_TAGLINE",
  "一次注册，通行所有授权网站"
);
export const COPYRIGHT_HOLDER = APP_NAME;
export const DOCUMENT_TITLE = `${APP_NAME} · 统一登录门户`;

/** 网站图标：统一使用 WebP 单格式（透明背景，512×512） */
export const FAVICON_WEBP = "/favicon.webp";

/** 兼容旧引用的主图标路径 */
export const FAVICON_PATH = FAVICON_WEBP;

/** 页面品牌主图（登录页/页头 Logo）：透明背景，512×512 */
export const APP_LOGO = "/brand-logo.webp";

// 上线前填入真实备案信息；留空时页脚不显示对应链接（避免展示占位假备案号）。
export const ICP_FILING_TEXT = envString("VITE_ICP_FILING_TEXT", "");
export const ICP_FILING_URL = envString(
  "VITE_ICP_FILING_URL",
  "https://beian.miit.gov.cn/"
);
export const ICP_FILING_ICON = envString("VITE_ICP_FILING_ICON", "/badges/icp.webp");
export const POLICE_FILING_TEXT = envString("VITE_POLICE_FILING_TEXT", "");
export const POLICE_FILING_URL = envString(
  "VITE_POLICE_FILING_URL",
  "https://beian.mps.gov.cn/"
);
export const POLICE_FILING_ICON = envString(
  "VITE_POLICE_FILING_ICON",
  "/badges/police.webp"
);

/**
 * 页脚附加链接（帮助中心/隐私政策/服务条款等），可用 VITE_FOOTER_LINKS
 * 以 JSON 数组覆盖，例如：[{"label":"帮助中心","href":"/help"}]。
 * 当前为空数组表示不展示。
 */
function footerLinksFromEnv(): { label: string; href: string }[] {
  const raw = envString("VITE_FOOTER_LINKS", "");
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is { label: string; href: string } =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as { label?: unknown }).label === "string" &&
        typeof (item as { href?: unknown }).href === "string"
    );
  } catch {
    return [];
  }
}

export const FOOTER_LINKS: { label: string; href: string }[] =
  footerLinksFromEnv();
