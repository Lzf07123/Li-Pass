import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { FloatingBackground } from "../components/FloatingBackground";
import { SiteFooter } from "../components/SiteFooter";
import {
  CONTACT_EMAIL,
  GITHUB_ISSUES_URL,
  LICENSE_NAME,
  LICENSE_URL,
} from "../lib/brand";

interface LegalSection {
  heading: string;
  children: ReactNode;
}

function contactChannel() {
  return (
    <>
      {CONTACT_EMAIL && (
        <p>
          邮箱：{" "}
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="font-medium text-primary transition-colors hover:text-primary-hover"
          >
            {CONTACT_EMAIL}
          </a>
        </p>
      )}
      {GITHUB_ISSUES_URL && (
        <p>
          问题反馈：{" "}
          <a
            href={GITHUB_ISSUES_URL}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary transition-colors hover:text-primary-hover"
          >
            GitHub Issues
          </a>
        </p>
      )}
      {!CONTACT_EMAIL && !GITHUB_ISSUES_URL && (
        <p>如有疑问，可通过服务页面提供的反馈渠道与我们联系。</p>
      )}
    </>
  );
}

const PRIVACY_SECTIONS: LegalSection[] = [
  {
    heading: "引言",
    children: (
      <p>
        本隐私政策说明 Li&Pass（统一身份提供商）如何收集、使用、存储与保护你的个人信息。使用本服务即表示你已阅读并理解本政策。
      </p>
    ),
  },
  {
    heading: "我们收集的信息",
    children: (
      <>
        <p>我们仅收集提供服务所必需的信息，包括：</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>账号信息：注册邮箱、昵称、头像、密码哈希（Argon2id 加盐）、两步验证绑定状态、恢复码哈希、可信设备标识。</li>
          <li>登录与安全信息：IP 地址、浏览器标识、登录与登出时间、会话与设备信息、安全审计日志与限流计数。</li>
          <li>授权网站信息：你授权或撤销的接入网站、OIDC 令牌签发记录与联邦登出记录。</li>
          <li>你主动提供的信息：站内消息、联系邮箱往来内容。</li>
          <li>本地存储：记住账号、主题偏好等设置；我们不保存明文密码。</li>
        </ul>
      </>
    ),
  },
  {
    heading: "我们如何使用信息",
    children: (
      <>
        <p>我们使用上述信息用于：</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>提供注册、登录、单点登录、两步验证与会话管理服务。</li>
          <li>保障账号安全，识别异常登录、滥用与攻击行为。</li>
          <li>改进服务体验、发送必要的服务通知。</li>
          <li>履行法律义务与合规要求。</li>
        </ul>
      </>
    ),
  },
  {
    heading: "信息共享",
    children: (
      <>
        <p>我们不会向任何第三方出售或出租你的个人信息。</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>仅在获得你授权时，向接入网站提供其申请范围内的 OIDC 声明（如稳定唯一标识、邮箱、昵称）。</li>
          <li>在法律要求、司法或行政机关依法调取时，按法定程序披露。</li>
          <li>委托处理方仅在必要范围内处理数据，并受保密义务约束。</li>
        </ul>
      </>
    ),
  },
  {
    heading: "Cookie 与本地存储",
    children: (
      <p>
        我们会使用会话 Cookie（如 lipass_session）与可信设备 Cookie（如
        lipass_trusted_device）维持登录状态；记住账号与主题偏好等设置保存在浏览器本地存储中。你可以通过浏览器设置管理或清除它们。
      </p>
    ),
  },
  {
    heading: "数据安全",
    children: (
      <p>
        我们通过传输加密（TLS）、密码加盐哈希（Argon2id）、敏感数据加密、访问控制、限流与审计日志等措施保护数据安全。任何安全措施都无法保证绝对安全，请妥善保管你的密码、恢复码与两步验证设备。
      </p>
    ),
  },
  {
    heading: "数据保留",
    children: (
      <p>
        账号存续期间，我们按服务需要保留相关信息；账号注销后，我们将按法律与技术要求删除或匿名化处理。审计日志按法定要求保留。
      </p>
    ),
  },
  {
    heading: "你的权利",
    children: (
      <p>
        你可以在用户中心查看与修改账号信息、管理两步验证与可信设备、撤销授权或注销账号。你也可以依法请求访问、更正、删除个人信息或对处理提出异议。
      </p>
    ),
  },
  {
    heading: "未成年人",
    children: (
      <p>
        本服务面向成年人，未满 14 周岁的未成年人不得注册。如发现未成年人注册，我们将依法删除相关账号与信息。
      </p>
    ),
  },
  {
    heading: "政策更新",
    children: (
      <p>
        本政策更新时，我们会在本页面发布并标注更新日期；重大变更会通过站内信或邮箱另行通知。
      </p>
    ),
  },
  {
    heading: "联系我们",
    children: (
      <>
        <p>如对本隐私政策或个人信息处理有疑问，可通过以下方式联系我们：</p>
        {contactChannel()}
      </>
    ),
  },
];

const TERMS_SECTIONS: LegalSection[] = [
  {
    heading: "服务说明",
    children: (
      <p>
        Li&Pass 提供统一账号注册、登录、单点登录（OIDC）、两步验证、会话与授权管理等功能。使用本服务即表示你同意本服务条款。
      </p>
    ),
  },
  {
    heading: "账号与安全责任",
    children: (
      <ul className="list-disc space-y-1 pl-5">
        <li>你应妥善保管密码、恢复码与两步验证设备，不得与他人共享账号。</li>
        <li>发现账号存在异常时，应立即修改密码、下线可疑设备并联系我们。</li>
        <li>因未妥善保管凭据导致的损失，由你自行承担相应责任。</li>
      </ul>
    ),
  },
  {
    heading: "可接受使用",
    children: (
      <ul className="list-disc space-y-1 pl-5">
        <li>不得利用本服务从事任何违法或侵权活动。</li>
        <li>不得攻击、干扰、逆向或滥用本服务及其基础设施。</li>
        <li>不得批量注册、爬取数据或伪造请求。</li>
        <li>不得利用本服务实施欺诈、钓鱼或传播恶意内容。</li>
      </ul>
    ),
  },
  {
    heading: "授权网站",
    children: (
      <p>
        是否授权接入网站由你自行决定。授权前请阅读该网站的隐私政策与服务条款；本平台对授权网站的内容、行为及其自身服务不承担责任。
      </p>
    ),
  },
  {
    heading: "知识产权",
    children: (
      <>
        <p>
          Li&Pass 品牌、界面与文档归相应权利人所有；代码按开源许可证提供。未经许可，不得以误导性方式使用本服务名称与标识。
        </p>
        {LICENSE_NAME && LICENSE_URL && (
          <p>
            开源协议：{" "}
            <a
              href={LICENSE_URL}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-primary transition-colors hover:text-primary-hover"
            >
              {LICENSE_NAME}
            </a>
          </p>
        )}
      </>
    ),
  },
  {
    heading: "服务可用性",
    children: (
      <p>
        我们会尽力保障服务的稳定运行，但服务可能因维护、升级、网络或不可抗力而暂停。本服务不构成对连续可用性的承诺。
      </p>
    ),
  },
  {
    heading: "免责与责任限制",
    children: (
      <p>
        在法律允许的最大范围内，我们不对因使用或无法使用本服务产生的间接、偶然或后果性损失承担责任；法律强制性规定另有要求的除外。
      </p>
    ),
  },
  {
    heading: "账号终止",
    children: (
      <p>
        如你违反本条款或适用法律，我们可暂停或终止向你提供服务。你也可以随时在用户中心注销账号。
      </p>
    ),
  },
  {
    heading: "条款变更",
    children: (
      <p>
        本条款更新时，我们会在本页面发布并标注更新日期。更新后继续使用本服务，视为你接受修订后的条款。
      </p>
    ),
  },
  {
    heading: "法律适用与争议",
    children: (
      <p>
        本条款适用中华人民共和国法律。因本服务产生的争议，双方应先行协商；协商不成的，提交有管辖权的人民法院解决。
      </p>
    ),
  },
  {
    heading: "联系我们",
    children: (
      <>
        <p>如对本服务条款有疑问，可通过以下方式联系我们：</p>
        {contactChannel()}
      </>
    ),
  },
];

const LEGAL_PAGES = {
  privacy: {
    title: "隐私政策",
    updatedAt: "2026-08-18",
    sections: PRIVACY_SECTIONS,
  },
  terms: {
    title: "服务条款",
    updatedAt: "2026-08-18",
    sections: TERMS_SECTIONS,
  },
} as const;

export function LegalPage({ kind }: { kind: keyof typeof LEGAL_PAGES }) {
  const page = LEGAL_PAGES[kind];

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      <FloatingBackground
        theme="auto"
        transparent
        shapeCount={4}
        opacity={0.5}
      />
      <AppHeader
        title={page.title}
        actions={
          <Link to="/" className="btn btn-secondary">
            返回首页
          </Link>
        }
      />
      <main className="relative mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
        <article className="card p-6 sm:p-10">
          <header className="border-b border-border/60 pb-5">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {page.title}
            </h1>
            <p className="mt-2 text-xs text-muted">
              最后更新：{page.updatedAt}
            </p>
          </header>
          <div className="mt-6 space-y-8">
            {page.sections.map((section) => (
              <section key={section.heading}>
                <h2 className="text-base font-semibold text-foreground">
                  {section.heading}
                </h2>
                <div className="mt-2 space-y-3 text-sm leading-6 text-muted">
                  {section.children}
                </div>
              </section>
            ))}
          </div>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}
