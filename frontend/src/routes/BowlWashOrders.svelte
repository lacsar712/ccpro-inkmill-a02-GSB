<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { bowlWashStatusLabel } from '../lib/labels';
  import type { BowlWashOrder, Mill } from '../lib/types';

  let rows: BowlWashOrder[] = [];
  let mills: Mill[] = [];
  let error = '';
  let millFilter = '';
  let selectedId: number | null = null;
  let syncMillStatus = false;
  let acting = false;

  function nowLocal(): string {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  let form = {
    millId: '',
    reason: '',
    plannedAt: nowLocal(),
    operatorName: '',
  };

  async function load() {
    error = '';
    try {
      const query = millFilter ? `?millId=${millFilter}` : '';
      [rows, mills] = await Promise.all([
        api<BowlWashOrder[]>(`/bowl-wash-orders${query}`),
        api<Mill[]>('/mills'),
      ]);
      if (!form.millId && mills[0]) form.millId = String(mills[0].id);
      if (selectedId && !rows.some((r) => r.id === selectedId)) selectedId = null;
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  $: selected = rows.find((r) => r.id === selectedId) || null;

  function millLabel(id: number): string {
    const m = mills.find((x) => x.id === id);
    return m ? `${m.millCode} (#${id})` : `#${id}`;
  }

  function millStatusOf(id: number): string | null {
    return mills.find((x) => x.id === id)?.status ?? null;
  }

  function reset() {
    form = {
      millId: mills[0] ? String(mills[0].id) : '',
      reason: '',
      plannedAt: nowLocal(),
      operatorName: '',
    };
  }

  async function create() {
    error = '';
    const payload = {
      millId: Number(form.millId),
      reason: form.reason,
      plannedAt: form.plannedAt,
      operatorName: form.operatorName,
    };
    try {
      const created = await api<BowlWashOrder>('/bowl-wash-orders', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      millFilter = '';
      reset();
      await load();
      selectedId = created.id;
    } catch (e) {
      error = e instanceof Error ? e.message : '创建失败';
    }
  }

  async function transition(path: string, withSync = false) {
    if (!selected) return;
    error = '';
    acting = true;
    try {
      await api(`/bowl-wash-orders/${selected.id}/${path}`, {
        method: 'POST',
        body: JSON.stringify(withSync ? { syncMillStatus: true } : {}),
      });
      syncMillStatus = false;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '流转失败';
    } finally {
      acting = false;
    }
  }

  async function voidOrder() {
    if (!selected) return;
    if (!confirm(`确认作废洗机工单 #${selected.id}？作废后不可恢复。`)) return;
    await transition('void');
  }
</script>

<header class="page-head">
  <h1>换钵洗机工单</h1>
  <p>同一研磨机同时只允许一个「待清洗 / 清洗中」工单；open → washing → done，非终态可作废</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>新建洗机工单</h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={form.millId}>
          {#each mills as m}
            <option value={String(m.id)}>
              {m.millCode}（{m.status === 'wash' ? '已 wash' : `机台 ${m.status}`}）
            </option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field">
      <label>计划时间<input type="datetime-local" bind:value={form.plannedAt} /></label>
    </div>
    <div class="field full"><label>洗机原因<input bind:value={form.reason} placeholder="如：换色换钵 / 批次结束例行清洗" /></label></div>
    <div class="field"><label>操作员<input bind:value={form.operatorName} /></label></div>
  </div>
  <div class="actions">
    <button class="btn-primary" on:click={create}>创建工单</button>
    <button class="btn-ghost" on:click={reset}>清空</button>
  </div>
</section>

<div class="split">
  <section class="panel list-panel">
    <div class="list-head">
      <h2>工单列表</h2>
      <label class="filter">
        按机台筛选
        <select bind:value={millFilter} on:change={load}>
          <option value="">全部机台</option>
          {#each mills as m}
            <option value={String(m.id)}>{m.millCode}</option>
          {/each}
        </select>
      </label>
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>研磨机</th>
          <th>计划时间</th>
          <th>状态</th>
          <th>操作员</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr class:selected={selectedId === row.id}>
            <td>{row.id}</td>
            <td>{row.millCode || millLabel(row.millId)}</td>
            <td>{row.plannedAt}</td>
            <td><span class="badge {row.status}">{bowlWashStatusLabel[row.status]}</span></td>
            <td>{row.operatorName}</td>
            <td class="ops">
              <button class="link-btn" on:click={() => (selectedId = row.id)}>详情</button>
            </td>
          </tr>
        {:else}
          <tr><td colspan="6">暂无工单</td></tr>
        {/each}
      </tbody>
    </table>
  </section>

  <section class="panel detail-panel">
    <h2>工单详情 / 流转</h2>
    {#if selected}
      <div class="detail">
        <div class="detail-row"><span>工单号</span><b>#{selected.id}</b></div>
        <div class="detail-row"><span>研磨机</span><b>{selected.millCode || millLabel(selected.millId)}</b></div>
        <div class="detail-row">
          <span>机台状态</span>
          <b class={millStatusOf(selected.millId) === 'wash' ? 'ok-text' : 'warn-text'}>
            {millStatusOf(selected.millId) || '?'}
            {millStatusOf(selected.millId) !== 'wash' ? '（非 wash，开始清洗需联动或先改机台）' : ''}
          </b>
        </div>
        <div class="detail-row"><span>计划时间</span><b>{selected.plannedAt}</b></div>
        <div class="detail-row"><span>创建时间</span><b>{selected.createdAt}</b></div>
        <div class="detail-row"><span>操作员</span><b>{selected.operatorName}</b></div>
        <div class="detail-row"><span>原因</span><b>{selected.reason}</b></div>
        <div class="detail-row">
          <span>当前状态</span>
          <span class="badge {selected.status}">{bowlWashStatusLabel[selected.status]}</span>
        </div>

        <div class="flow">
          {#if selected.status === 'open'}
            <label class="sync-line">
              <input type="checkbox" bind:checked={syncMillStatus} />
              工单内联动：开始清洗同时把研磨机置为 wash
            </label>
            <div class="actions">
              <button class="btn-primary" disabled={acting} on:click={() => transition('start', syncMillStatus)}>
                开始清洗（open → washing）
              </button>
              <button class="btn-ghost" disabled={acting} on:click={voidOrder}>作废</button>
            </div>
          {:else if selected.status === 'washing'}
            <div class="actions">
              <button class="btn-primary" disabled={acting} on:click={() => transition('complete')}>
                完成清洗（washing → done）
              </button>
              <button class="btn-ghost" disabled={acting} on:click={voidOrder}>作废</button>
            </div>
          {:else}
            <div class="muted">终态（{bowlWashStatusLabel[selected.status]}），不可再流转。</div>
          {/if}
        </div>
      </div>
    {:else}
      <p class="muted">点击左侧「详情」查看工单并执行状态流转。</p>
    {/if}
  </section>
</div>

<style>
  .split {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 1rem;
    align-items: start;
  }

  .list-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .list-head h2 {
    margin: 0;
  }

  .filter {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    color: var(--steel);
  }

  .filter select {
    border: 1px solid var(--line);
    background: rgba(0, 0, 0, 0.35);
    color: white;
    padding: 0.4rem 0.5rem;
  }

  tr.selected {
    background: rgba(192, 57, 43, 0.12);
  }

  .detail {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    font-size: 0.9rem;
    border-bottom: 1px dashed var(--line);
    padding-bottom: 0.45rem;
  }

  .detail-row span {
    color: var(--steel);
    white-space: nowrap;
  }

  .detail-row b {
    text-align: right;
    font-weight: 500;
  }

  .ok-text {
    color: var(--ok);
  }

  .warn-text {
    color: var(--vermillion-400);
  }

  .flow {
    margin-top: 0.6rem;
  }

  .sync-line {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
    font-size: 0.82rem;
    color: var(--steel);
    margin-bottom: 0.7rem;
  }

  @media (max-width: 960px) {
    .split {
      grid-template-columns: 1fr;
    }
  }
</style>
