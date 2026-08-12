import { useEffect, useState } from "react";

import { adminClientsApi } from "../api/client";
import { adminBlocksApi } from "../api/client";
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

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <h1 className="mb-6 text-2xl font-bold">授权网站管理</h1>
      <form onSubmit={handleCreate} className="mb-8 space-y-3 rounded-xl bg-white p-6 shadow">
        <label className="block">
          名称
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          回调地址（每行一个）
          <textarea
            value={redirectUris}
            onChange={(e) => setRedirectUris(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          首页地址（应用广场“进入”链接）
          <input
            value={homeUrl}
            onChange={(e) => setHomeUrl(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            placeholder="http://localhost:3001"
          />
        </label>
        <label className="block">
          登出地址（取消授权时签出该网站）
          <input
            value={logoutUri}
            onChange={(e) => setLogoutUri(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            placeholder="http://localhost:3001/logout"
          />
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
          />
          公开客户端（无 secret，仅 PKCE）
        </label>
        {secret && (
          <p className="rounded bg-yellow-50 p-2 text-sm">
            请立即保存 client_secret（只显示一次）：<code>{secret}</code>
          </p>
        )}
      {error && <p className="text-red-600">{error}</p>}
        <button type="submit" className="rounded bg-blue-600 p-2 text-white">
          创建应用
        </button>
      </form>
      {removeTarget && (
        <div className="mb-4 flex items-center gap-2 rounded border border-red-200 bg-red-50 p-3">
          <span className="text-sm">
            确定删除应用“{removeTarget.name}”吗？其授权记录与黑名单将一并删除。
          </span>
          <button onClick={confirmRemove} className="rounded bg-red-600 p-2 text-white">
            确认删除
          </button>
          <button
            onClick={() => setRemoveTarget(null)}
            className="rounded bg-gray-200 p-2"
          >
            取消
          </button>
        </div>
      )}
      <ul className="space-y-2">
        {clients.map((client) => (
          <li key={client.id} className="rounded-xl bg-white p-4 shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold">{client.name}</p>
                <p className="text-sm text-gray-500">{client.client_id}</p>
              </div>
              <button
                onClick={() => setRemoveTarget(client)}
                className="rounded bg-red-600 p-2 text-sm text-white"
              >
                删除应用
              </button>
            </div>
            <div className="mt-3 border-t pt-3">
              <p className="mb-2 text-sm font-semibold">黑名单</p>
              <ul className="mb-2 space-y-1">
                {(blocks[client.id] ?? []).map((block) => (
                  <li key={block.id} className="flex items-center justify-between text-sm">
                    <span>
                      {block.email ?? block.user_id}（{block.reason || "无原因"}）
                    </span>
                    <button
                      onClick={() => removeBlock(client.id, block.id)}
                      className="text-red-600"
                    >
                      解封
                    </button>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                <input
                  value={blockEmail[client.id] ?? ""}
                  onChange={(e) =>
                    setBlockEmail({ ...blockEmail, [client.id]: e.target.value })
                  }
                  placeholder="封禁邮箱"
                  className="flex-1 rounded border p-1 text-sm"
                />
                <input
                  value={blockReason[client.id] ?? ""}
                  onChange={(e) =>
                    setBlockReason({ ...blockReason, [client.id]: e.target.value })
                  }
                  placeholder="原因"
                  className="flex-1 rounded border p-1 text-sm"
                />
                <button
                  onClick={() => addBlock(client.id)}
                  className="rounded bg-red-600 p-1 text-sm text-white"
                >
                  封禁
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
