<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { bowlWashStatusLabel, millStatusLabel } from '../lib/labels';
  import type { BowlWashOrder, BowlWashStatus, Mill } from '../lib/types';

  let rows: BowlWashOrder[] = [];
  let mills: Mill[] = [];
  let error = '';
  let filterMill = 'all';
  let selectedId: number | null = null;
  let setMillWash = false;
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
      const q = filterMill !== 'all' ? `?millId=${filterMill}` : '';
      [rows, mills] = await Promise.all([
        api<BowlWashOrder[]>(`/bowl-wash-orders${q}`),
        api<Mill[]>('/mills'),
      ]);
      if (!form.millId && mills[0]) form.millId = String(mills[0].id);
      if (selectedId && !rows.some((r) => r.id === selectedId)) {
        selectedId = null;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : '加载失败';
    }
  }

  onMount(load);

  function millOf(id: number): Mill | undefined {
    return mills.find((m) => m.id === id);
  }

  function millLabel(id: number): string {
    const m = millOf(id);
    return m ? `${m.millCode} (#${m.id})` : `#${id}`;
  }

  $: selected = rows.find((r) => r.id === selectedId) || null;
  $: selectedMill = selected ? millOf(selected.millId) : null;
  $: isTerminal = (s: BowlWashStatus) => s === 'done' || s === 'void';

  function resetForm() {
    form = {
      millId: mills[0] ? String(mills[0].id) : '',
      reason: '',
      plannedAt: nowLocal(),
      operatorName: '',
    };
  }

  async function create() {
    error = '';
    try {
      await api('/bowl-wash-orders', {
        method: 'POST',
        body: JSON.stringify({
          millId: Number(form.millId),
          reason: form.reason,
          plannedAt: form.plannedAt,
          operatorName: form.operatorName,
        }),
      });
      resetForm();
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '创建失败';
    }
  }

  async function transition(action: 'start' | 'finish' | 'void') {
    if (!selected) return;
    if (action === 'void' && !confirm('确认作废该洗机工单？作废后不可恢复。')) return;
    error = '';
    acting = true;
    try {
      const payload: Record<string, unknown> = { action };
      if (action === 'start' && setMillWash) payload.setMillWash = true;
      const updated = await api<BowlWashOrder>(
        `/bowl-wash-orders/${selected.id}/transitions`,
        { method: 'POST', body: JSON.stringify(payload) },
      );
      setMillWash = false;
      // load() 同时刷新工单与机台（机台可能被联动置为 wash，列表标记也随之更新）
      await load();
      selectedId = updated.id;
    } catch (e) {
      error = e instanceof Error ? e.message : '流转失败';
    } finally {
      acting = false;
    }
  }
</script>

<header class="page-head">
  <h1>换钵洗机工单</h1>
  <p>同一机台同时只允许一个待洗机 / 洗机中工单；待洗机 → 洗机中 → 已完成，非终态可作废</p>
</header>

{#if error}
  <div class="err">{error}</div>
{/if}

<section class="panel">
  <h2>新增洗机工单</h2>
  <div class="fields">
    <div class="field">
      <label>研磨机
        <select bind:value={form.millId}>
          {#each mills as m}
            <option value={String(m.id)}>
              {m.millCode}（{millStatusLabel[m.status]}）
            </option>
          {/each}
        </select>
      </label>
    </div>
    <div class="field"><label>计划时间<input type="datetime-local" bind:value={form.plannedAt} /></label></div>
    <div class="field span2"><label>洗机原因<input bind:value={form.reason} placeholder="如：换色洗钵 / 批次结束常规洗机" /></label></div>
    <div class="field"><label>操作员<input bind:value={form.operatorName} /></label></div>
  </div>
  <div class="actions">
    <button class="btn-primary" on:click={create}>创建工单</button>
  </div>
</section>

<section class="panel">
  <div class="list-head">
    <h2>工单列表</h2>
    <label class="filter">按机台筛选
      <select bind:value={filterMill} on:change={load}>
        <option value="all">全部机台</option>
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
        <th>原因</th>
        <th>计划时间</th>
        <th>操作员</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr class:row-active={selectedId === row.id}>
          <td>{row.id}</td>
          <td>{millLabel(row.millId)}</td>
          <td>{row.reason}</td>
          <td>{row.plannedAt}</td>
          <td>{row.operatorName}</td>
          <td><span class="badge wash-order {row.status}">{bowlWashStatusLabel[row.status]}</span></td>
          <td class="ops">
            <button class="link-btn" on:click={() => (selectedId = row.id)}>详情/流转</button>
          </td>
        </tr>
      {:else}
        <tr><td colspan="7">暂无工单</td></tr>
      {/each}
    </tbody>
  </table>
</section>

{#if selected}
  <section class="panel detail">
    <h2>工单 #{selected.id} · 详情流转</h2>
    <div class="detail-grid">
      <div><span class="k">研磨机</span><span class="v">{millLabel(selected.millId)}</span></div>
      <div>
        <span class="k">机台状态</span>
        <span class="v">
          {#if selectedMill}
            <span class="badge {selectedMill.status}">{millStatusLabel[selectedMill.status]}</span>
          {/if}
        </span>
      </div>
      <div class="span2"><span class="k">洗机原因</span><span class="v">{selected.reason}</span></div>
      <div><span class="k">计划时间</span><span class="v">{selected.plannedAt}</span></div>
      <div><span class="k">操作员</span><span class="v">{selected.operatorName}</span></div>
      <div><span class="k">开始洗机</span><span class="v">{selected.startedAt ?? '—'}</span></div>
      <div><span class="k">结束时间</span><span class="v">{selected.finishedAt ?? '—'}</span></div>
      <div>
        <span class="k">当前状态</span>
        <span class="v"><span class="badge wash-order {selected.status}">{bowlWashStatusLabel[selected.status]}</span></span>
      </div>
    </div>

    {#if !isTerminal(selected.status)}
      <div class="transitions">
        {#if selected.status === 'open'}
          <label class="link-check">
            <input type="checkbox" bind:checked={setMillWash} />
            联动把机台置为「清洗」
            {#if selectedMill && selectedMill.status !== 'wash'}
              <em>（机台当前为{millStatusLabel[selectedMill.status]}，不勾选则开始会返回 409）</em>
            {/if}
          </label>
          <button class="btn-primary" disabled={acting} on:click={() => transition('start')}>
            开始洗机
          </button>
        {/if}
        {#if selected.status === 'washing'}
          <button class="btn-primary" disabled={acting} on:click={() => transition('finish')}>
            完成洗机
          </button>
        {/if}
        <button class="btn-ghost" disabled={acting} on:click={() => transition('void')}>
          作废工单
        </button>
      </div>
    {:else}
      <p class="muted terminal-note">该工单已处于终态（{bowlWashStatusLabel[selected.status]}），不可再流转。</p>
    {/if}
  </section>
{/if}

<style>
  .list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .filter {
    font-size: 0.85rem;
    color: var(--steel);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .row-active {
    outline: 1px solid rgba(231, 76, 60, 0.5);
  }

  .wash-order.open {
    border-color: var(--vermillion-700);
    color: var(--vermillion-400);
  }

  .wash-order.washing {
    color: var(--paper);
    border-color: var(--paper);
  }

  .wash-order.done {
    color: var(--steel);
  }

  .wash-order.void {
    color: var(--steel);
    opacity: 0.6;
    text-decoration: line-through;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.7rem 2rem;
    margin-bottom: 1.2rem;
  }

  .detail-grid .span2 {
    grid-column: span 2;
  }

  .detail-grid .k {
    display: block;
    font-size: 0.75rem;
    color: var(--steel);
    margin-bottom: 0.15rem;
  }

  .detail-grid .v {
    display: block;
  }

  .transitions {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    border-top: 1px solid var(--line);
    padding-top: 1rem;
  }

  .link-check {
    font-size: 0.85rem;
    color: var(--steel);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 1;
  }

  .link-check em {
    color: var(--vermillion-400);
    font-style: normal;
  }

  .terminal-note {
    margin: 0;
    border-top: 1px solid var(--line);
    padding-top: 1rem;
  }

  .field.span2 {
    grid-column: span 2;
  }
</style>
