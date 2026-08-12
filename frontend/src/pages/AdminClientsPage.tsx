import { useEffect, useState } from "react";

import { adminBlocksApi, adminClientsApi } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { useToast } from "../hooks/useToast";
import type { ClientBlockOut, ClientOut } from "../api/types";

export function AdminClientsPage() {
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [name, setName] = useState("");
  const [homeUrl, setHomeUrl] = useState("");
  const [logoutUri, setLogoutUri] = useState("");
  const [redirectUris, setRedirectUris] = useState("");
  // 默认机密客户端：服务端 OIDC 对接需要 client_id + client_secret；
  // 仅纯前端 SPA（PKCE）才需要勾选“公开客户端”。
  const [isPublic, setIsPublic] = useState(false);
  const [blocks, setBlocks] = useState<Record<string, ClientBlockOut[]>>({});
  const [blockEmail, setBlockEmail] = useState<Record<string, string>>({});
  const [blockReason, setBlockReason] = useState<Record<string, string>>({});
  const [removeTarget, setRemoveTarget] = useState<ClientOut | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ClientOut | null>(null);
  const [resetTarget, setResetTarget] = useState<ClientOut | null>(null);
  const [secretModal, setSecretModal] = useState<{
    name: string;
    client_id: string;
    secret: string;
  } | null>(null);
  const toast = useToast();

  useEffect(() => {
    adminClientsApi
      .list()
      .then(async (list) => {
        setClients(list);
        const entries = await Promise.all(
          list.map(async (client) => [client.id, await adminBlocksApi.list(client.id)] as const)
        );
        setBlocks(Object.fromEntries(entries));
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败"),
      );
  }, [toast]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await adminClientsApi.create({
        name,
        home_url: homeUrl || null,
        logout_uri: logoutUri || null,
        redirect_uris: redirectUris
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        public: isPublic,
      });
      setClients([result.client, ...clients]);
      setSecretModal({
        name: result.client.name,
        client_id: result.client.client_id,
        secret: result.client_secret ?? "",
      });
      setName("");
      setHomeUrl("");
      setLogoutUri("");
      setRedirectUris("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function addBlock(clientId: string) {
    try {
      const created = await adminBlocksApi.add(clientId, {
        email: blockEmail[clientId] ?? "",
        reason: blockReason[clientId] ?? "",
      });
      setBlocks({ ...blocks, [clientId]: [created, ...(blocks[clientId] ?? [])] });
      setBlockEmail({ ...blockEmail, [clientId]: "" });
      setBlockReason({ ...blockReason, [clientId]: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "封禁失败");
    }
  }

  async function removeBlock(clientId: string, blockId: string) {
    try {
      await adminBlocksApi.remove(clientId, blockId);
      setBlocks({
        ...blocks,
        [clientId]: (blocks[clientId] ?? []).filter((block) => block.id !== blockId),
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "解封失败");
    }
  }

  async function confirmRemove() {
    if (!removeTarget) return;
    try {
      await adminClientsApi.remove(removeTarget.id);
      setClients(clients.filter((client) => client.id !== removeTarget.id));
      setRemoveTarget(null);
      toast.success(`应用“${removeTarget.name}”已删除`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  function startEdit(client: ClientOut) {
    setEditingId(client.id);
    setEditDraft({ ...client });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft(null);
  }

  function updateDraft(patch: Partial<ClientOut>) {
    setEditDraft((draft) => (draft ? { ...draft, ...patch } : draft));
  }

  async function saveEdit() {
    if (!editDraft) return;
    try {
      const updated = await adminClientsApi.update(editDraft.id, {
        name: editDraft.name,
        description: editDraft.description,
        logo_url: editDraft.logo_url || null,
        home_url: editDraft.home_url || null,
        logout_uri: editDraft.logout_uri || null,
        redirect_uris: editDraft.redirect_uris,
        scopes: editDraft.scopes,
        require_consent_every_time: editDraft.require_consent_every_time,
        is_active: editDraft.is_active,
      });
      setClients(clients.map((client) => (client.id === updated.id ? updated : client)));
      setEditingId(null);
      setEditDraft(null);
      toast.success(`应用“${updated.name}”已保存`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function toggleActive(client: ClientOut) {
    try {
      const updated = await adminClientsApi.update(client.id, {
        is_active: !client.is_active,
      });
      setClients(clients.map((item) => (item.id === updated.id ? updated : item)));
      toast.success(
        `应用“${updated.name}”已${updated.is_active ? "启用" : "停用"}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function resetSecret(client: ClientOut) {
    try {
      const result = await adminClientsApi.resetSecret(client.id);
      setResetTarget(null);
      setSecretModal({
        name: client.name,
        client_id: client.client_id,
        secret: result.client_secret ?? "",
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置密钥失败");
    }
  }

  async function copyText(text: string, label: string) {
    if (!text) return;
    if (!navigator.clipboard) {
      toast.error("当前浏览器不支持一键复制，请手动选择复制");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label}已复制到剪贴板`);
    } catch {
      toast.error("复制失败，请手动选择复制");
    }
  }

  function startResetSecret(client: ClientOut) {
    setResetTarget(client);
  }

  return (
    <section className="space-y-6">
      <h2 className="text-lg font-semibold text-foreground">授权网站管理</h2>

      <form onSubmit={handleCreate} className="card space-y-4 p-6">
        <h3 className="text-sm font-semibold text-foreground">添加授权网站</h3>
        <label className="block">
          <span className="label">名称</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input"
            required
          />
        </label>
        <label className="block">
          <span className="label">回调地址（每行一个）</span>
          <textarea
            value={redirectUris}
            onChange={(e) => setRedirectUris(e.target.value)}
            className="input min-h-20 resize-y"
            required
          />
        </label>
        <label className="block">
          <span className="label">首页地址（应用广场“进入”链接）</span>
          <input
            value={homeUrl}
            onChange={(e) => setHomeUrl(e.target.value)}
            className="input"
            placeholder="https://your-site.example"
          />
        </label>
        <label className="block">
          <span className="label">登出地址（取消授权时签出该网站）</span>
          <input
            value={logoutUri}
            onChange={(e) => setLogoutUri(e.target.value)}
            className="input"
            placeholder="https://your-site.example/logout"
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          公开客户端（无 secret，仅 PKCE）
        </label>
        <p className="text-xs text-muted">
          不勾选“公开客户端”时会生成机密客户端并返回
          client_secret，用于服务端 OIDC 对接。
        </p>
        <button type="submit" className="btn btn-primary">
          创建应用
        </button>
      </form>

      <ul className="space-y-3">
        {clients.map((client) => (
          <li key={client.id} className="card card-interactive p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 font-semibold text-foreground">
                  {client.name}
                  {client.has_secret ? (
                    <span className="badge badge-muted">机密客户端</span>
                  ) : (
                    <span className="badge badge-primary">公开客户端</span>
                  )}
                  {client.is_active ? (
                    <span className="badge badge-success">启用中</span>
                  ) : (
                    <span className="badge badge-muted">已停用</span>
                  )}
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-xs text-muted">
                  <span className="break-all">{client.client_id}</span>
                  <button
                    type="button"
                    onClick={() => void copyText(client.client_id, "client_id")}
                    className="btn-link text-xs"
                  >
                    复制
                  </button>
                </p>
                {client.description && (
                  <p className="mt-1.5 text-sm text-foreground/80">
                    {client.description}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {client.has_secret && (
                  <button
                    onClick={() => startResetSecret(client)}
                    className="btn btn-secondary"
                    title="重新生成 client_secret，旧密钥立即失效"
                  >
                    重置密钥
                  </button>
                )}
                <button onClick={() => startEdit(client)} className="btn btn-secondary">
                  编辑
                </button>
                <button onClick={() => toggleActive(client)} className="btn btn-secondary">
                  {client.is_active ? "停用" : "启用"}
                </button>
                {!client.is_active && (
                  <span className="text-xs text-muted">已停用，无法发起授权</span>
                )}
                <button
                  onClick={() => setRemoveTarget(client)}
                  className="btn btn-danger"
                >
                  删除应用
                </button>
              </div>
            </div>

            {client.require_consent_every_time && (
              <p className="mt-3 text-xs text-warning">
                配置：每次授权都需用户确认
              </p>
            )}

            {editingId === client.id && editDraft && (
              <fieldset className="animate-fade-up mt-4 space-y-3 rounded-xl border border-primary/30 bg-primary-soft p-4">
                <legend className="px-1.5 text-sm font-semibold text-primary">
                  编辑应用
                </legend>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    <span className="label">名称</span>
                    <input
                      value={editDraft.name}
                      onChange={(e) => updateDraft({ name: e.target.value })}
                      className="input"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="label">图标地址</span>
                    <input
                      value={editDraft.logo_url ?? ""}
                      onChange={(e) => updateDraft({ logo_url: e.target.value || null })}
                      placeholder="https://…/logo.png"
                      className="input"
                    />
                  </label>
                </div>
                <label className="block text-sm">
                  <span className="label">描述</span>
                  <input
                    value={editDraft.description}
                    onChange={(e) => updateDraft({ description: e.target.value })}
                    className="input"
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm">
                    <span className="label">首页地址</span>
                    <input
                      value={editDraft.home_url ?? ""}
                      onChange={(e) => updateDraft({ home_url: e.target.value || null })}
                      className="input"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="label">登出地址</span>
                    <input
                      value={editDraft.logout_uri ?? ""}
                      onChange={(e) => updateDraft({ logout_uri: e.target.value || null })}
                      className="input"
                    />
                  </label>
                </div>
                <label className="block text-sm">
                  <span className="label">回调地址（每行一个）</span>
                  <textarea
                    value={editDraft.redirect_uris.join("\n")}
                    onChange={(e) =>
                      updateDraft({
                        redirect_uris: e.target.value
                          .split("\n")
                          .map((item) => item.trim())
                          .filter(Boolean),
                      })
                    }
                    className="input min-h-20 resize-y"
                  />
                </label>
                <label className="block text-sm">
                  <span className="label">授权范围（逗号分隔）</span>
                  <input
                    value={editDraft.scopes.join(", ")}
                    onChange={(e) =>
                      updateDraft({
                        scopes: e.target.value
                          .split(/[,，\s]+/)
                          .map((item) => item.trim())
                          .filter(Boolean),
                      })
                    }
                    className="input"
                  />
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={editDraft.require_consent_every_time}
                    onChange={(e) =>
                      updateDraft({ require_consent_every_time: e.target.checked })
                    }
                    className="h-4 w-4 accent-primary"
                  />
                  每次授权都需用户确认
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={editDraft.is_active}
                    onChange={(e) => updateDraft({ is_active: e.target.checked })}
                    className="h-4 w-4 accent-primary"
                  />
                  启用该网站（停用后无法发起授权）
                </label>
                <div className="flex flex-wrap gap-2">
                  <button onClick={saveEdit} className="btn btn-primary">
                    保存修改
                  </button>
                  <button onClick={cancelEdit} className="btn btn-secondary">
                    取消
                  </button>
                </div>
              </fieldset>
            )}

            <div className="mt-4 border-t border-border pt-4">
              <p className="mb-2 text-sm font-semibold text-foreground">黑名单</p>
              <ul className="mb-2 space-y-1">
                {(blocks[client.id] ?? []).map((block) => (
                  <li
                    key={block.id}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <span className="text-foreground">
                      {block.email ?? block.user_id}（{block.reason || "无原因"}）
                    </span>
                    <button
                      onClick={() => removeBlock(client.id, block.id)}
                      className="btn-link text-sm"
                    >
                      解封
                    </button>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <input
                  value={blockEmail[client.id] ?? ""}
                  onChange={(e) =>
                    setBlockEmail({ ...blockEmail, [client.id]: e.target.value })
                  }
                  placeholder="封禁邮箱"
                  className="input-sm min-w-40 flex-1"
                />
                <input
                  value={blockReason[client.id] ?? ""}
                  onChange={(e) =>
                    setBlockReason({ ...blockReason, [client.id]: e.target.value })
                  }
                  placeholder="原因"
                  className="input-sm min-w-32 flex-1"
                />
                <button
                  onClick={() => addBlock(client.id)}
                  className="btn btn-danger px-3 py-1.5 text-xs"
                >
                  封禁
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={removeTarget !== null}
        title="删除应用"
        message={
          removeTarget && (
            <span>
              确定删除应用“{removeTarget.name}”吗？其授权记录与黑名单将一并删除。
            </span>
          )
        }
        confirmLabel="确认删除"
        onConfirm={confirmRemove}
        onCancel={() => setRemoveTarget(null)}
      />

      <ConfirmDialog
        open={resetTarget !== null}
        title="重置 client_secret"
        message={
          resetTarget && (
            <span>
              确定重置应用“{resetTarget.name}”的 client_secret 吗？
              旧密钥将立即失效，需要同步更新接入方配置。
            </span>
          )
        }
        confirmLabel="确认重置"
        onConfirm={() => resetTarget && void resetSecret(resetTarget)}
        onCancel={() => setResetTarget(null)}
      />

      <Modal
        open={secretModal !== null}
        onClose={() => setSecretModal(null)}
        title={secretModal ? `${secretModal.name} 的接入凭据` : "接入凭据"}
        intent="warning"
        footer={
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setSecretModal(null)}
            >
              我已保存
            </button>
          </>
        }
      >
        <p className="mb-3 text-warning">
          {secretModal?.secret
            ? "client_secret 只显示一次，请立即保存到安全的位置。"
            : "该客户端为公开客户端，仅需 client_id，配合 PKCE 使用。"}
        </p>
        <div className="space-y-3">
          <div>
            <span className="label">client_id</span>
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 break-all rounded-lg bg-surface-2 p-3 font-mono text-xs text-foreground">
                {secretModal?.client_id}
              </code>
              <button
                type="button"
                onClick={() =>
                  void copyText(secretModal?.client_id ?? "", "client_id")
                }
                className="btn btn-secondary px-3 py-1.5 text-xs"
              >
                复制
              </button>
            </div>
          </div>
          {secretModal?.secret && (
            <div>
              <span className="label">client_secret</span>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 break-all rounded-lg bg-surface-2 p-3 font-mono text-xs text-foreground">
                  {secretModal.secret}
                </code>
                <button
                  type="button"
                  onClick={() =>
                    void copyText(secretModal?.secret ?? "", "client_secret")
                  }
                  className="btn btn-secondary px-3 py-1.5 text-xs"
                >
                  复制
                </button>
              </div>
            </div>
          )}
        </div>
        <p className="mt-3 text-xs text-muted">
          将 client_id 与 client_secret 配置到授权网站的 OIDC
          客户端中；公开客户端无需 secret。
        </p>
      </Modal>
    </section>
  );
}
