import { useEffect, useState, useMemo, useCallback } from "react";
import {
  fetchFinancialSummary,
  fetchFinancialDaily,
  fetchFinancialProducts,
  fetchFinancialProductDaily,
  fetchAdvertisingSummary,
  fetchAdvertisingProducts,
  fetchProductDrawer,
  makePeriod,
  makeCustomPeriod,
  syncAll,
  updateCostPrice,
  type Period,
} from "../api/client";

const fmt = (n: number) => n?.toLocaleString("ru-RU", { maximumFractionDigits: 0 }) ?? "0";
const fmtR = (n: number) => fmt(Math.round(n ?? 0)) + " ₽";
const fmtP = (n: number) => (n ?? 0).toFixed(1) + "%";

interface FinSummary {
  period: { start: string; end: string; days: number };
  sales_count: number; sales_revenue: number;
  returns_count: number; returns_revenue: number;
  logistics_cost: number; rebill_logistics_cost: number;
  storage_cost: number; acceptance_cost: number;
  deduction_cost: number; penalty_cost: number;
  acquiring_sales: number; acquiring_returns: number;
  commission_sales: number; commission_returns: number;
  payout_sales: number; payout_returns: number;
  net_payout: number; net_qty: number;
  cost_price_estimate: number; profit_estimate: number;
  order_count: number; order_sum: number;
}

interface FinDaily {
  date: string; sales_count: number; sales_revenue: number;
  returns_count: number; returns_revenue: number;
  net_payout: number; profit_estimate: number;
  order_count: number;
}

interface FinProduct {
  nm_id: number; vendor_code: string; title: string; brand: string;
  sales_count: number; sales_revenue: number;
  returns_count: number; returns_revenue: number;
  net_payout: number; profit_estimate: number;
  order_count: number; order_sum: number;
  cost_price_estimate: number; logistics_cost: number; storage_cost: number;
}

interface AdSummary {
  views: number; clicks: number; ctr: number; cpm: number; cpc: number;
  spend: number; add_to_cart: number; ad_orders: number;
  total_orders: number; total_order_sum: number; revenue: number;
  cpo: number; drr: number;
}

interface AdProduct {
  nm_id: number; vendor_code: string; title: string; brand: string;
  views: number; clicks: number; ctr: number; cpm: number; cpc: number;
  spend: number; atc: number; ad_orders: number;
  total_orders: number; total_order_sum: number; revenue: number;
  cpo: number; drr: number;
}

function DailyChart({ data, dataKey, color, label, height = 80 }: {
  data: any[]; dataKey: string; color: string; label: string; height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (!data.length) return null;
  const vals = data.map(d => Number(d[dataKey]) || 0);
  const max = Math.max(...vals.map(Math.abs), 1);
  const w = 100 / vals.length;
  const hasNeg = vals.some(v => v < 0);
  const mid = height / 2;
  return (
    <div style={{position:"relative"}}>
      <div style={{fontSize:11,color:"#888",marginBottom:4,fontWeight:500}}>{label}</div>
      {hover !== null && (
        <div style={{position:"absolute",top:0,right:0,fontSize:11,background:"#1a1a2e",color:"white",padding:"2px 8px",borderRadius:4,zIndex:2}}>
          {data[hover]?.date?.slice(5)} : {fmtR(vals[hover])}
        </div>
      )}
      <svg width="100%" height={height} viewBox={`0 0 100 ${height}`} preserveAspectRatio="none"
        onMouseLeave={() => setHover(null)}>
        {hasNeg && <line x1="0" y1={mid} x2="100" y2={mid} stroke="#e5e7eb" strokeWidth="0.3"/>}
        {vals.map((v, i) => {
          if (hasNeg) {
            const h = Math.abs(v) / max * (mid - 2);
            const y = v >= 0 ? mid - h : mid;
            return <rect key={i} x={i*w+0.3} y={y} width={w-0.6} height={Math.max(h,0.5)}
              fill={v>=0?color:"#ef4444"} rx="0.5" opacity={hover===i?1:0.8}
              onMouseEnter={()=>setHover(i)} style={{cursor:"crosshair"}}/>;
          }
          const h = v / max * (height - 4);
          return <rect key={i} x={i*w+0.3} y={height-h-2} width={w-0.6} height={Math.max(h,0.5)}
            fill={color} rx="0.5" opacity={hover===i?1:0.8}
            onMouseEnter={()=>setHover(i)} style={{cursor:"crosshair"}}/>;
        })}
      </svg>
      <div style={{display:"flex",justifyContent:"space-between",fontSize:9,color:"#bbb",marginTop:2}}>
        <span>{data[0]?.date?.slice(5)}</span>
        <span>{data[data.length-1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}

function DrawerBarChart({ data, dataKey, color, isRub = false }: {
  data: any[]; dataKey: string; color: string; isRub?: boolean;
}) {
  if (!data.length) return null;
  const vals = data.map(d => Number(d[dataKey]) || 0);
  const max = Math.max(...vals, 1);
  const fv = (v: number) => {
    if (v === 0) return "";
    if (isRub) return v >= 1000 ? (v/1000).toFixed(1)+"k" : Math.round(v).toString();
    return Math.round(v).toString();
  };
  return (
    <div>
      <div style={{display:"flex",alignItems:"flex-end",gap:2,height:50}}>
        {vals.map((v, i) => {
          const h = Math.max(v / max * 40, v > 0 ? 3 : 0);
          return (
            <div key={i} style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"flex-end",height:"100%"}}>
              <div style={{fontSize:9,fontWeight:700,color,marginBottom:2,lineHeight:1}}>{fv(v)}</div>
              <div style={{width:"70%",height:h,background:color,borderRadius:2,opacity:0.85}}/>
            </div>
          );
        })}
      </div>
      <div style={{display:"flex",marginTop:3,gap:2}}>
        {data.map((d: any, i: number) => (
          <div key={i} style={{flex:1,textAlign:"center",fontSize:7,color:"#aaa"}}>{d.date?.slice(8)}</div>
        ))}
      </div>
    </div>
  );
}

const PRESETS = [
  { label: "Вчера", days: 1 },
  { label: "7д", days: 7 },
  { label: "14д", days: 14 },
  { label: "30д", days: 30 },
  { label: "Апрель", from: "2026-04-01", to: "2026-04-28" },
];

type TabMode = "main" | "costs" | "efficiency" | "ads";

export default function Dashboard() {
  const [summary, setSummary] = useState<FinSummary | null>(null);
  const [daily, setDaily] = useState<FinDaily[]>([]);
  const [products, setProducts] = useState<FinProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [activePreset, setActivePreset] = useState(3);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [sortKey, setSortKey] = useState<string>("order_count");
  const [sortDir, setSortDir] = useState<"asc"|"desc">("desc");
  const [search, setSearch] = useState("");
  const [editCost, setEditCost] = useState<{[k:number]:string}>({});
  const [tabMode, setTabMode] = useState<TabMode>("main");
  const [drawerNm, setDrawerNm] = useState<number|null>(null);
  const [drawerDaily, setDrawerDaily] = useState<any[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerOrderDaily, setDrawerOrderDaily] = useState<any[]>([]);
  const [adSummary, setAdSummary] = useState<AdSummary | null>(null);
  const [adProducts, setAdProducts] = useState<AdProduct[]>([]);

  const period: Period = useMemo(() => {
    const preset = PRESETS[activePreset];
    if (preset && "from" in preset && preset.from) return makeCustomPeriod(preset.from, preset.to!);
    if (preset && "days" in preset) return makePeriod(preset.days);
    if (customFrom && customTo) return makeCustomPeriod(customFrom, customTo);
    return makePeriod(30);
  }, [activePreset, customFrom, customTo]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, d, p, adS, adP] = await Promise.all([
        fetchFinancialSummary(period),
        fetchFinancialDaily(period),
        fetchFinancialProducts(period),
        fetchAdvertisingSummary(period).catch(() => null),
        fetchAdvertisingProducts(period).catch(() => ({ items: [] })),
      ]);
      setSummary(s);
      setDaily(d.daily || []);
      setProducts(Array.isArray(p) ? p : p.products || []);
      setAdSummary(adS);
      setAdProducts(adP?.items || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [period]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!drawerNm) { setDrawerDaily([]); setDrawerOrderDaily([]); return; }
    setDrawerLoading(true);
    Promise.all([
      fetchFinancialProductDaily(drawerNm, period).catch(() => ({ daily: [] })),
      fetchProductDrawer(drawerNm, period).catch(() => ({ daily: [], totals: {} })),
    ]).then(([fin, drawer]) => {
      setDrawerDaily(fin.daily || fin.data || (Array.isArray(fin) ? fin : []));
      setDrawerOrderDaily(drawer.daily || []);
    }).catch(() => { setDrawerDaily([]); setDrawerOrderDaily([]); })
      .finally(() => setDrawerLoading(false));
  }, [drawerNm, period]);

  const handleSync = async () => {
    setSyncing(true);
    try { await syncAll(30); alert("Синхронизация запущена!"); }
    catch { alert("Ошибка"); }
    setSyncing(false);
  };

  const saveCost = async (nmId: number) => {
    const val = parseFloat(editCost[nmId] || "0");
    if (val > 0) { await updateCostPrice(nmId, val); load(); }
  };

  const adMap = Object.fromEntries(adProducts.map(a => [a.nm_id, a]));
  const getAdVal = (nmId: number, key: string): any => {
    const a = adMap[nmId];
    if (!a) return 0;
    const m: Record<string, any> = {
      _ad_views: a.views, _ad_cpm: a.cpm, _ad_clicks: a.clicks,
      _ad_ctr: a.ctr, _ad_cpc: a.cpc, _ad_spend: a.spend,
      _ad_cpo: a.cpo, _ad_drr: a.drr,
    };
    return m[key] ?? 0;
  };

  const sortedProducts = useMemo(() => {
    let list = [...products];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(p => p.vendor_code?.toLowerCase().includes(q) || p.title?.toLowerCase().includes(q) || String(p.nm_id).includes(q));
    }
    if (tabMode === "ads" && !sortKey.startsWith("_ad_")) {
      // On ads tab, filter to only products with ad data
      list = list.filter(p => adMap[p.nm_id]);
    }
    list.sort((a: any, b: any) => {
      let va, vb;
      if (sortKey.startsWith("_ad_")) {
        va = getAdVal(a.nm_id, sortKey);
        vb = getAdVal(b.nm_id, sortKey);
      } else {
        va = a[sortKey] ?? 0;
        vb = b[sortKey] ?? 0;
      }
      if (typeof va === "string") return sortDir === "desc" ? vb.localeCompare(va) : va.localeCompare(vb);
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return list;
  }, [products, sortKey, sortDir, search, tabMode, adProducts]);

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortKey(key); setSortDir("desc"); }
  };
  const si = (key: string) => sortKey === key ? (sortDir === "desc" ? " ▼" : " ▲") : "";

  const TABS: Record<TabMode, {key:string;label:string;fmt?:(p:any)=>string;color?:(p:any)=>string}[]> = {
    main: [
      { key:"vendor_code", label:"Артикул" },
      { key:"order_count", label:"Заказы", fmt: p=>fmt(p.order_count || 0) },
      { key:"sales_count", label:"Выкупы", fmt: p=>fmt(p.sales_count) },
      { key:"buyout_percent", label:"Выкуп %", fmt: p=>{
        const pct = p.order_count>0 ? p.sales_count/p.order_count*100 : 0;
        return fmtP(pct);
      }, color: p => {
        const pct = p.order_count>0 ? p.sales_count/p.order_count*100 : 0;
        return pct<50?"#ef4444":pct<70?"#f59e0b":"#22c55e";
      }},
      { key:"sales_revenue", label:"Выручка", fmt: p=>fmtR(p.sales_revenue) },
      { key:"net_payout", label:"Выплата", fmt: p=>fmtR(p.net_payout) },
      { key:"profit_estimate", label:"Прибыль", fmt: p=>fmtR(p.profit_estimate),
        color: p=>p.profit_estimate>=0?"#16a34a":"#ef4444" },
    ],
    costs: [
      { key:"vendor_code", label:"Артикул" },
      { key:"order_count", label:"Заказы", fmt: p=>fmt(p.order_count || 0) },
      { key:"sales_count", label:"Выкупы", fmt: p=>fmt(p.sales_count) },
      { key:"logistics_cost", label:"Логистика", fmt: p=>fmtR(p.logistics_cost) },
      { key:"storage_cost", label:"Хранение", fmt: p=>fmtR(p.storage_cost) },
      { key:"cost_price_estimate", label:"Себест.", fmt: p=>fmtR(p.cost_price_estimate) },
      { key:"net_payout", label:"Выплата", fmt: p=>fmtR(p.net_payout) },
      { key:"profit_estimate", label:"Прибыль", fmt: p=>fmtR(p.profit_estimate),
        color: p=>p.profit_estimate>=0?"#16a34a":"#ef4444" },
    ],
    efficiency: [
      { key:"vendor_code", label:"Артикул" },
      { key:"order_count", label:"Заказы", fmt: p=>fmt(p.order_count || 0) },
      { key:"sales_count", label:"Выкупы", fmt: p=>fmt(p.sales_count) },
      { key:"sales_revenue", label:"Выручка", fmt: p=>fmtR(p.sales_revenue) },
      { key:"_margin_pct", label:"Маржа%", fmt: p => {
        const pct = p.sales_revenue > 0 ? p.profit_estimate / p.sales_revenue * 100 : 0;
        return fmtP(pct);
      }, color: p => {
        const pct = p.sales_revenue > 0 ? p.profit_estimate / p.sales_revenue * 100 : 0;
        return pct > 10 ? "#16a34a" : pct > 0 ? "#f59e0b" : "#ef4444";
      }},
      { key:"_profit_per_sale", label:"Приб/шт", fmt: p => {
        const net = p.sales_count - p.returns_count;
        return net > 0 ? fmtR(p.profit_estimate / net) : "—";
      }},
      { key:"_return_rate", label:"Возврат%", fmt: p => {
        return p.sales_count > 0 ? fmtP(p.returns_count / p.sales_count * 100) : "0%";
      }, color: p => {
        const pct = p.sales_count > 0 ? p.returns_count / p.sales_count * 100 : 0;
        return pct > 30 ? "#ef4444" : pct > 20 ? "#f59e0b" : "#16a34a";
      }},
      { key:"profit_estimate", label:"Прибыль", fmt: p=>fmtR(p.profit_estimate),
        color: p=>p.profit_estimate>=0?"#16a34a":"#ef4444" },
    ],
    ads: [
      { key:"vendor_code", label:"Артикул", fmt: (p:any)=>{const a=adMap[p.nm_id]; return p.vendor_code || ""} },
      { key:"_ad_views", label:"Показы", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmt(a.views) : "—"} },
      { key:"_ad_cpm", label:"CPM", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtR(a.cpm) : "—"} },
      { key:"_ad_clicks", label:"Клики", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmt(a.clicks) : "—"} },
      { key:"_ad_ctr", label:"CTR", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtP(a.ctr) : "—"} },
      { key:"_ad_cpc", label:"CPC", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtR(a.cpc) : "—"} },
      { key:"_ad_spend", label:"Расход", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtR(a.spend) : "—"},
        color: (p:any)=>{const a=adMap[p.nm_id]; return a && a.spend>0 ? "#d946ef" : "#888"} },
      { key:"order_count", label:"Заказы", fmt: (p:any)=>fmt(p.order_count || 0) },
      { key:"_ad_cpo", label:"CPO", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtR(a.cpo) : "—"} },
      { key:"_ad_drr", label:"ДРР", fmt: (p:any)=>{const a=adMap[p.nm_id]; return a ? fmtP(a.drr) : "—"},
        color: (p:any)=>{const a=adMap[p.nm_id]; return a && a.drr>5 ? "#ef4444" : "#16a34a"} },
    ],
  };

  const drawerProduct = products.find(p => p.nm_id === drawerNm);

  if (loading) return <div style={{display:"flex",justifyContent:"center",alignItems:"center",height:"100vh",fontSize:16,color:"#888"}}>Загрузка...</div>;
  if (!summary) return <div style={{padding:40,textAlign:"center"}}>Нет данных</div>;

  const s = summary;
  const returnRate = s.sales_count > 0 ? s.returns_count / s.sales_count * 100 : 0;
  const profitMargin = s.sales_revenue > 0 ? s.profit_estimate / s.sales_revenue * 100 : 0;

  return (
    <div style={{display:"flex",height:"100vh",overflow:"hidden",fontFamily:"-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif",background:"#f0f2f5"}}>
      <div style={{flex:1,overflow:"auto",padding:"16px 20px"}}>

        {/* HEADER */}
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
          <div>
            <h1 style={{margin:0,fontSize:20,fontWeight:700,color:"#1a1a2e"}}>WB Аналитика</h1>
            <span style={{fontSize:11,color:"#999"}}>Факт WB | {s.period.start} — {s.period.end} ({s.period.days} дн.)</span>
          </div>
          <button onClick={handleSync} disabled={syncing}
            style={{padding:"6px 14px",borderRadius:6,border:"none",background:"#4f46e5",color:"white",cursor:"pointer",fontSize:12,fontWeight:500}}>
            {syncing ? "⏳" : "🔄"} Синхронизация
          </button>
        </div>

        {/* PERIOD */}
        <div style={{display:"flex",gap:5,marginBottom:14,alignItems:"center",flexWrap:"wrap"}}>
          {PRESETS.map((p, i) => (
            <button key={i} onClick={() => { setActivePreset(i); setCustomFrom(""); setCustomTo(""); }}
              style={{padding:"5px 12px",borderRadius:6,fontSize:12,cursor:"pointer",
                border: activePreset===i ? "2px solid #4f46e5" : "1px solid #d1d5db",
                background: activePreset===i ? "#eef2ff" : "white",
                color: activePreset===i ? "#4f46e5" : "#555",
                fontWeight: activePreset===i ? 600 : 400}}>
              {p.label}
            </button>
          ))}
          <span style={{color:"#ccc",fontSize:12,margin:"0 4px"}}>|</span>
          <input type="date" value={customFrom} onChange={e=>{setCustomFrom(e.target.value);setActivePreset(-1);}}
            style={{padding:"4px 6px",borderRadius:4,border:"1px solid #d1d5db",fontSize:12}} />
          <span style={{color:"#ccc"}}>—</span>
          <input type="date" value={customTo} onChange={e=>{setCustomTo(e.target.value);setActivePreset(-1);}}
            style={{padding:"4px 6px",borderRadius:4,border:"1px solid #d1d5db",fontSize:12}} />
        </div>

        {/* KPI CARDS */}
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit, minmax(145px, 1fr))",gap:8,marginBottom:14}}>
          {[
            {label:"Заказы",value:fmt(s.order_count || 0),sub:fmtR(s.order_sum || 0),color:"#3b82f6"},
            {label:"Выкупы",value:fmt(s.sales_count),sub:fmtR(s.sales_revenue),color:"#4f46e5"},
            {label:"Выкуп %",value:fmtP(s.order_count>0 ? s.sales_count/s.order_count*100 : 0),sub:fmt(s.sales_count)+" из "+fmt(s.order_count)+" заказов",color:(s.order_count>0 && s.sales_count/s.order_count*100<70)?"#ef4444":"#22c55e"},
            
            {label:"Прибыль",value:fmtR(s.profit_estimate),sub:"маржа "+fmtP(profitMargin),color:s.profit_estimate>=0?"#16a34a":"#ef4444"},
            {label:"Логистика",value:fmtR(s.logistics_cost+s.rebill_logistics_cost),sub:s.sales_revenue>0?fmtP((s.logistics_cost+s.rebill_logistics_cost)/s.sales_revenue*100)+" от выручки":"",color:"#8b5cf6"},
            {label:"Хранение",value:fmtR(s.storage_cost),sub:"штраф: "+fmtR(s.penalty_cost),color:"#6366f1"},
            {label:"Комиссия WB",value:fmtR(s.commission_sales),sub:"возвр: "+fmtR(s.commission_returns),color:"#ec4899"},
            {label:"Эквайринг",value:fmtR(s.acquiring_sales),sub:"возвр: "+fmtR(s.acquiring_returns),color:"#f97316"},
            {label:"Рекл. расход",value:fmtR(adSummary?.spend||0),sub:"CPO: "+fmtR(adSummary?.cpo||0),color:"#d946ef"},
            {label:"ДРР",value:fmtP(adSummary?.drr||0),sub:"расход/выручка",color:((adSummary?.drr||0)>5)?"#ef4444":"#10b981"},
          ].map((c,i) => (
            <div key={i} style={{background:"white",borderRadius:8,padding:"12px 14px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)",borderLeft:"3px solid "+c.color}}>
              <div style={{fontSize:10,color:"#888",fontWeight:500,textTransform:"uppercase",letterSpacing:"0.5px"}}>{c.label}</div>
              <div style={{fontSize:17,fontWeight:700,color:"#1a1a2e",marginTop:2}}>{c.value}</div>
              <div style={{fontSize:10,color:"#aaa",marginTop:1}}>{c.sub}</div>
            </div>
          ))}
        </div>



        {/* DAILY CHARTS */}
        {daily.length > 0 && (
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginBottom:14}}>
            <div style={{background:"white",borderRadius:8,padding:"10px 12px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)"}}>
              <DailyChart data={daily} dataKey="sales_revenue" color="#4f46e5" label="Продажи по дням"/>
            </div>
            <div style={{background:"white",borderRadius:8,padding:"10px 12px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)"}}>

            </div>
            <div style={{background:"white",borderRadius:8,padding:"10px 12px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)"}}>
              <DailyChart data={daily} dataKey="profit_estimate" color="#16a34a" label="Прибыль по дням"/>
            </div>
          </div>
        )}

        {/* ATTENTION */}
        {(() => {
          const losers = [...products].filter(p=>p.profit_estimate<0).sort((a,b)=>a.profit_estimate-b.profit_estimate).slice(0,5);
          const highRet = [...products].filter(p=>p.returns_count>0&&p.sales_count>2)
            .sort((a,b)=>(b.returns_count/b.sales_count)-(a.returns_count/a.sales_count)).slice(0,5);
          if (!losers.length && !highRet.length) return null;
          return (
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:14}}>
              {losers.length>0 && (
                <div style={{background:"white",borderRadius:8,padding:"10px 14px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)",borderLeft:"3px solid #ef4444"}}>
                  <div style={{fontSize:11,fontWeight:600,color:"#ef4444",marginBottom:6}}>Убыточные товары</div>
                  {losers.map(p=>(
                    <div key={p.nm_id} onClick={()=>setDrawerNm(p.nm_id)}
                      style={{display:"flex",justifyContent:"space-between",fontSize:11,padding:"2px 0",borderBottom:"1px solid #f8f8f8",cursor:"pointer"}}>
                      <span style={{color:"#444"}}>{p.vendor_code?.slice(0,22)}</span>
                      <span style={{color:"#ef4444",fontWeight:600}}>{fmtR(p.profit_estimate)}</span>
                    </div>
                  ))}
                </div>
              )}
              {highRet.length>0 && (
                <div style={{background:"white",borderRadius:8,padding:"10px 14px",boxShadow:"0 1px 2px rgba(0,0,0,0.05)",borderLeft:"3px solid #f59e0b"}}>
                  <div style={{fontSize:11,fontWeight:600,color:"#f59e0b",marginBottom:6}}>Высокий возврат</div>
                  {highRet.map(p=>(
                    <div key={p.nm_id} onClick={()=>setDrawerNm(p.nm_id)}
                      style={{display:"flex",justifyContent:"space-between",fontSize:11,padding:"2px 0",borderBottom:"1px solid #f8f8f8",cursor:"pointer"}}>
                      <span style={{color:"#444"}}>{p.vendor_code?.slice(0,22)}</span>
                      <span style={{color:"#f59e0b",fontWeight:600}}>{p.returns_count}/{p.sales_count} ({fmtP(p.returns_count/p.sales_count*100)})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })()}

        {/* PRODUCTS TABLE */}
        <div style={{background:"white",borderRadius:8,boxShadow:"0 1px 2px rgba(0,0,0,0.05)",overflow:"hidden"}}>
          <div style={{padding:"10px 14px",borderBottom:"1px solid #eee",display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:8}}>
            <div style={{display:"flex",gap:4}}>
              {([["main","Основное"],["costs","Расходы"],["efficiency","Эффективность"],["ads","Реклама"]] as [TabMode,string][]).map(([k,l]) => (
                <button key={k} onClick={()=>{setTabMode(k); if(k==="ads"){setSortKey("_ad_spend");setSortDir("desc");}else if(k==="main"){setSortKey("order_count");setSortDir("desc");}}}
                  style={{padding:"4px 10px",borderRadius:4,fontSize:11,cursor:"pointer",
                    border:tabMode===k?"1px solid #4f46e5":"1px solid #e5e7eb",
                    background:tabMode===k?"#eef2ff":"white",color:tabMode===k?"#4f46e5":"#666",fontWeight:tabMode===k?600:400}}>
                  {l}
                </button>
              ))}
            </div>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <span style={{fontSize:12,color:"#888"}}>Товары ({sortedProducts.length})</span>
              <input placeholder="Поиск..." value={search} onChange={e=>setSearch(e.target.value)}
                style={{padding:"5px 10px",borderRadius:5,border:"1px solid #d1d5db",fontSize:12,width:200}}/>
            </div>
          </div>
          <div style={{overflowX:"auto",maxHeight:"50vh",overflowY:"auto"}}>
            <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
              <thead>
                <tr style={{background:"#fafbfc",position:"sticky",top:0,zIndex:1}}>
                  {TABS[tabMode].map(h=>(
                    <th key={h.key} onClick={()=>toggleSort(h.key)}
                      style={{padding:"7px 8px",textAlign:"left",borderBottom:"2px solid #e5e7eb",whiteSpace:"nowrap",
                        cursor:"pointer",userSelect:"none",fontSize:10,color:"#777",fontWeight:600}}>
                      {h.label}{si(h.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedProducts.map(p=>(
                  <tr key={p.nm_id} onClick={()=>setDrawerNm(drawerNm===p.nm_id?null:p.nm_id)}
                    style={{borderBottom:"1px solid #f5f5f5",cursor:"pointer",
                      background:drawerNm===p.nm_id?"#f0f4ff":"transparent",transition:"background 0.15s"}}>
                    {TABS[tabMode].map(h=>{
                      if (h.key === "vendor_code") return (
                        <td key={h.key} style={{padding:"6px 8px",fontWeight:600,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}} title={p.title}>
                          {p.vendor_code}
                        </td>
                      );
                      if (h.key === "cost_price_estimate") return (
                        <td key={h.key} style={{padding:"6px 8px"}}>
                          <input style={{width:60,padding:"1px 3px",border:"1px solid #e5e7eb",borderRadius:3,fontSize:11}}
                            value={editCost[p.nm_id] ?? Math.round(p.cost_price_estimate/Math.max(p.sales_count-p.returns_count,1)) ?? ""}
                            onChange={e=>{e.stopPropagation();setEditCost({...editCost,[p.nm_id]:e.target.value});}}
                            onClick={e=>e.stopPropagation()} onBlur={()=>saveCost(p.nm_id)} placeholder="0"/>
                        </td>
                      );
                      const val = h.fmt ? h.fmt(p) : String((p as any)[h.key] ?? "");
                      const clr = h.color ? h.color(p) : "#333";
                      return (
                        <td key={h.key} style={{padding:"6px 8px",color:clr,fontWeight:h.key==="profit_estimate"?700:400}}>
                          {val}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{marginTop:10,fontSize:10,color:"#ccc",textAlign:"center"}}>
          Факт WB | {s.period.start} — {s.period.end} | Продаж: {s.sales_count} | Возвратов: {s.returns_count}
        </div>
      </div>

      {/* DRAWER */}
      {drawerNm && drawerProduct && (
        <div style={{width:380,borderLeft:"1px solid #e5e7eb",background:"white",overflow:"auto",
          boxShadow:"-2px 0 8px rgba(0,0,0,0.05)",padding:16,flexShrink:0}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
            <div style={{fontSize:14,fontWeight:700,color:"#1a1a2e"}}>{drawerProduct.vendor_code}</div>
            <button onClick={()=>setDrawerNm(null)}
              style={{background:"none",border:"none",fontSize:18,cursor:"pointer",color:"#999"}}>✕</button>
          </div>
          <div style={{fontSize:11,color:"#888",marginBottom:12}}>{drawerProduct.title}</div>

          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,marginBottom:16}}>
            {[
              {l:"Заказы",v:fmt(drawerProduct.order_count || 0)},
              {l:"Выкупы",v:fmt(drawerProduct.sales_count)},
              {l:"Возвраты",v:fmt(drawerProduct.returns_count)},
              {l:"Выручка",v:fmtR(drawerProduct.sales_revenue)},
              {l:"Выплата",v:fmtR(drawerProduct.net_payout)},
              {l:"Логистика",v:fmtR(drawerProduct.logistics_cost)},
              {l:"Себест.",v:fmtR(drawerProduct.cost_price_estimate)},
            ].map((kp,i)=>(
              <div key={i} style={{background:"#f9fafb",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:9,color:"#999",fontWeight:500,textTransform:"uppercase"}}>{kp.l}</div>
                <div style={{fontSize:14,fontWeight:600,color:"#1a1a2e"}}>{kp.v}</div>
              </div>
            ))}
            <div style={{gridColumn:"1/3",background:drawerProduct.profit_estimate>=0?"#f0fdf4":"#fef2f2",borderRadius:6,padding:"8px 10px"}}>
              <div style={{fontSize:9,color:"#999",fontWeight:500,textTransform:"uppercase"}}>Прибыль</div>
              <div style={{fontSize:18,fontWeight:700,color:drawerProduct.profit_estimate>=0?"#16a34a":"#ef4444"}}>{fmtR(drawerProduct.profit_estimate)}</div>
            </div>
          </div>

          {drawerLoading ? (
            <div style={{textAlign:"center",padding:20,color:"#999"}}>Загрузка...</div>
          ) : drawerOrderDaily.length > 0 ? (
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              <div style={{background:"#f0f4ff",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:9,fontWeight:600,color:"#3b82f6",marginBottom:4}}>ЗАКАЗЫ, шт</div>
                <DrawerBarChart data={drawerOrderDaily} dataKey="order_count" color="#3b82f6"/>
              </div>
              <div style={{background:"#f5f3ff",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:9,fontWeight:600,color:"#8b5cf6",marginBottom:4}}>ВЫКУПЫ, шт</div>
                <DrawerBarChart data={drawerOrderDaily} dataKey="buyout_count" color="#8b5cf6"/>
              </div>
              <div style={{background:"#fdf4ff",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:9,fontWeight:600,color:"#d946ef",marginBottom:4}}>РЕКЛ. РАСХОД</div>
                <DrawerBarChart data={drawerOrderDaily} dataKey="ad_spend" color="#d946ef" isRub={true}/>
              </div>
              <div style={{background:"#eff6ff",borderRadius:6,padding:"8px 10px"}}>
                <div style={{fontSize:9,fontWeight:600,color:"#0ea5e9",marginBottom:4}}>CPO (расход/заказы)</div>
                <DrawerBarChart data={drawerOrderDaily.map((d: any) => ({...d, cpo: d.order_count > 0 ? d.ad_spend / d.order_count : 0}))} dataKey="cpo" color="#0ea5e9" isRub={true}/>
              </div>
              {/* Summary stats */}
              {(() => {
                const totalOrders = drawerOrderDaily.reduce((s: number, d: any) => s + (d.order_count || 0), 0);
                const totalBuyouts = drawerOrderDaily.reduce((s: number, d: any) => s + (d.buyout_count || 0), 0);
                const totalAdSpend = drawerOrderDaily.reduce((s: number, d: any) => s + (d.ad_spend || 0), 0);
                const totalOrderSum = drawerOrderDaily.reduce((s: number, d: any) => s + (d.order_sum || 0), 0);
                const avgPrice = totalOrders > 0 ? totalOrderSum / totalOrders : 0;
                const cpo = totalOrders > 0 ? totalAdSpend / totalOrders : 0;
                return (
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:4,marginTop:4}}>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>ИТОГО ЗАКАЗОВ</div>
                      <div style={{fontSize:13,fontWeight:700}}>{fmt(totalOrders)}</div>
                    </div>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>ИТОГО ВЫКУПОВ</div>
                      <div style={{fontSize:13,fontWeight:700}}>{fmt(totalBuyouts)}</div>
                    </div>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>РЕКЛ. РАСХОД</div>
                      <div style={{fontSize:13,fontWeight:700,color:"#d946ef"}}>{fmtR(totalAdSpend)}</div>
                    </div>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>CPO</div>
                      <div style={{fontSize:13,fontWeight:700,color:"#0ea5e9"}}>{fmtR(cpo)}</div>
                    </div>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>ДРР</div>
                      <div style={{fontSize:13,fontWeight:700,color:totalOrderSum>0&&totalAdSpend/totalOrderSum*100>5?"#ef4444":"#16a34a"}}>{totalOrderSum>0?fmtP(totalAdSpend/totalOrderSum*100):"—"}</div>
                    </div>
                    <div style={{background:"#f9fafb",borderRadius:4,padding:"6px 8px"}}>
                      <div style={{fontSize:8,color:"#999"}}>СУММА ЗАКАЗОВ</div>
                      <div style={{fontSize:13,fontWeight:700}}>{fmtR(totalOrderSum)}</div>
                    </div>
                  </div>
                );
              })()}
            </div>
          ) : drawerDaily.length > 0 ? (
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              <div style={{background:"#f9fafb",borderRadius:6,padding:"8px 10px"}}>
                <DailyChart data={drawerDaily} dataKey="sales_revenue" color="#4f46e5" label="Выкупы" height={70}/>
              </div>
              <div style={{background:"#f9fafb",borderRadius:6,padding:"8px 10px"}}>
                <DailyChart data={drawerDaily} dataKey="net_payout" color="#0ea5e9" label="Выплаты" height={70}/>
              </div>
              <div style={{background:"#f9fafb",borderRadius:6,padding:"8px 10px"}}>
                <DailyChart data={drawerDaily} dataKey="profit_estimate" color="#16a34a" label="Прибыль" height={70}/>
              </div>
            </div>
          ) : (
            <div style={{textAlign:"center",padding:20,fontSize:12,color:"#bbb"}}>Нет дневных данных</div>
          )}
        </div>
      )}
    </div>
  );
}