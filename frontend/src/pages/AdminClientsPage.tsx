import { useEffect, useState } from "react";

import { adminBlocksApi, adminClientsApi } from "../api/client";
import type { ClientBlockOut, ClientOut } from "../api/types";

export function AdminClientsPage() {
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [name, setName] = useState("");
  const [homeUrl, setHomeUrl] = useState("");
  const [logoutUri, setLogoutUri] = useState("");
  const [redirectUris, setRedirectUris] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [blocks, setBlocks] = useState<Record<string, ClientBlockOut[]>>({});
  const [blockEmail, setBlockEmail] = useState<Record<string, string>>({});
  const [blockReason, setBlockReason] = useState<Record<string, string>>({});
  const [removeTarget, setRemoveTarget] = useState<ClientOut | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ClientOut | null>(null);
  const [secretResult, setSecretResult] = useState<{
    name: string;
    secret: string;
  } | null>(null);

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
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSecret(null);
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
      setSecret(result.client_secret);
      setName("");
      setHomeUrl("");
      setLogoutUri("");
      setRedirectUris("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function addBlock(clientId: string) {
    setError("");
    try {
      const created = await adminBlocksApi.add(clientId, {
        email: blockEmail[clientId] ?? "",
        reason: blockReason[clientId] ?? "",
      });
      setBlocks({ ...blocks, [clientId]: [created, ...(blocks[clientId] ?? [])] });
      setBlockEmail({ ...blockEmail, [clientId]: "" });
      setBlockReason({ ...blockReason, [clientId]: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "封禁失败");
    }
  }

  async function removeBlock(clientId: string, blockId: string) {
    setError("");
    try {
      await adminBlocksApi.remove(clientId, blockId);
      setBlocks({
        ...blocks,
        [clientId]: (blocks[clientId] ?? []).filter((block) => block.id !== blockId),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "解封失败");
    }
  }

  async function confirmRemove() {
    if (!removeTarget) return;
    setError("");
    try {
      await adminClientsApi.remove(removeTarget.id);
      setClients(clients.filter((client) => client.id !== removeTarget.id));
      setRemoveTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  function startEdit(client: ClientOut) {
    setEditingId(client.id);
    setEditDraft({ ...client });
    setSecretResult(null);
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
    setError("");
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function toggleActive(client: ClientOut) {
    setError("");
    try {
      const updated = await adminClientsApi.update(client.id, {
        is_active: !client.is_active,
      });
      setClients(clients.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function resetSecret(client: ClientOut) {
    setError("");
    setSecretResult(null);
    try {
      const result = await adminClientsApi.resetSecret(client.id);
      setSecretResult({
        name: client.name,
        secret: result.client_secret ?? "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置密钥失败");
    }
  }

  return (
    <section className="space-y-6">
      <h2 className="text-lg font-semibold text-foreground">授权网站管理</h2>

      {secretResult && (
        <p className="alert alert-warning">
          <span className="break-all">
            已重置 <strong>{secretResult.name}</strong> 的 client_secret（只显示一次）：
            <code className="ml-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono">
              {secretResult.secret}
            </code>
          </span>
        </p>
      )}

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
        {secret && (
          <p className="alert alert-warning">
            <span className="break-all">
              请立即保存 client_secret（只显示一次）：
              <code className="ml-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono">
                {secret}
              </code>
            </span>
          </p>
        )}
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary">
          创建应用
        </button>
      </form>

      {removeTarget && (
        <div className="alert alert-error">
          <span>
            确定删除应用“{removeTarget.name}”吗？其授权记录与黑名单将一并删除。
          </span>
          <button onClick={confirmRemove} className="btn btn-danger">
            确认删除
          </button>
          <button
            onClick={() => setRemoveTarget(null)}
            className="btn btn-secondary"
          >
            取消
          </button>
        </div>
      )}

      <ul className="space-y-3">
        {clients.map((client) => (
          <li key={client.id} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 font-semibold text-foreground">
                  {client.name}
                  {client.is_active ? (
                    <span className="badge badge-success">启用中</span>
                  ) : (
                    <span className="badge badge-muted">已停用</span>
                  )}
                </p>
                <p className="mt-0.5 font-mono text-xs text-muted">{client.client_id}</p>
                {client.description && (
                  <p className="mt-1.5 text-sm text-foreground/80">
                    {client.description}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
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
              <fieldset className="mt-4 space-y-3 rounded-xl border border-primary/30 bg-primary-soft p-4">
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
                  <button
                    onClick={() => resetSecret(client)}
                    className="btn btn-secondary ml-auto"
                    title="为机密客户端重新生成 client_secret"
                  >
                    重置密钥
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
    </section>
  );
}
