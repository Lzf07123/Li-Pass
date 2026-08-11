import { useEffect, useState } from "react";

import { adminClientsApi } from "../api/client";
import type { ClientOut } from "../api/types";

export function AdminClientsPage() {
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [name, setName] = useState("");
  const [redirectUris, setRedirectUris] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminClientsApi
      .list()
      .then(setClients)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSecret(null);
    try {
      const result = await adminClientsApi.create({
        name,
        redirect_uris: redirectUris
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        public: isPublic,
      });
      setClients([result.client, ...clients]);
      setSecret(result.client_secret);
      setName("");
      setRedirectUris("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
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
      <ul className="space-y-2">
        {clients.map((client) => (
          <li key={client.id} className="rounded-xl bg-white p-4 shadow">
            <p className="font-semibold">{client.name}</p>
            <p className="text-sm text-gray-500">{client.client_id}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
