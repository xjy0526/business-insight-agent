import {
  bidRangeRows,
  poiProductCompareRows,
  productAdCandidates,
  productAdTrace,
  recallRows,
} from "../data/mockData.js";
import { Card, DataTable, Pill } from "./ui.jsx";

export default function ProductAds() {
  return (
    <div className="space-y-6">
      <section className="flex items-end justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.18em] text-aiBlue">
            Product-level ads decision system
          </p>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-ink">
            商品级广告增长工作台
          </h2>
          <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-muted">
            主推品排序、ROI 出价守护、Query-SKU 召回和 POI vs 商品级广告对比均来自
            synthetic demo data。
          </p>
        </div>
        <Pill tone="green">Deterministic demo</Pill>
      </section>

      <section className="grid grid-cols-[1.35fr_0.9fr] gap-6">
        <Card
          className="p-6"
          subtitle="Product Growth Score combines CVR, GMV share, PCVR, ROI and risk."
          title="主推品排序"
        >
          <div className="mt-5">
            <DataTable
              columns={[
                { key: "rank", label: "Rank" },
                { key: "product", label: "Product" },
                { key: "cvr", label: "CVR" },
                { key: "gmvShare", label: "GMV Share" },
                { key: "pcvr", label: "PCVR" },
                { key: "roi", label: "ROI" },
                { key: "risk", label: "Risk" },
              ]}
              rows={productAdCandidates}
            />
          </div>
        </Card>

        <Card
          className="p-6"
          subtitle="CPC bounds are calculated from PCVR, price, margin and target ROI."
          title="ROI 出价守护"
        >
          <div className="mt-5">
            <DataTable
              columns={[
                { key: "product", label: "Product" },
                { key: "targetRoi", label: "Target ROI" },
                { key: "profitCpc", label: "Profit CPC" },
                { key: "range", label: "Range" },
                { key: "action", label: "Action" },
              ]}
              rows={bidRangeRows}
            />
          </div>
          <p className="mt-4 text-xs font-semibold leading-5 text-muted">
            当目标 ROI 高于历史 ROI 时，界面只展示 watch/down_bid 等谨慎动作，不输出强结论。
          </p>
        </Card>
      </section>

      <section className="grid grid-cols-[1.1fr_1fr] gap-6">
        <Card
          className="p-6"
          subtitle="Exact demo recall is tried first; TF-IDF fallback is marked as uncertain."
          title="Query-SKU 召回"
        >
          <div className="mt-5">
            <DataTable
              columns={[
                { key: "query", label: "Query" },
                { key: "product", label: "Product" },
                { key: "path", label: "Path" },
                { key: "score", label: "Score" },
                { key: "match", label: "Matched Terms" },
              ]}
              rows={recallRows}
            />
          </div>
        </Card>

        <Card
          className="p-6"
          subtitle="Comparison uses synthetic baselines for demonstration."
          title="POI vs 商品级广告"
        >
          <div className="mt-5">
            <DataTable
              columns={[
                { key: "campaign", label: "Campaign" },
                { key: "ctr", label: "CTR" },
                { key: "cvr", label: "CVR" },
                { key: "orders", label: "Orders" },
                { key: "roi", label: "ROI" },
              ]}
              rows={poiProductCompareRows}
            />
          </div>
        </Card>
      </section>

      <Card
        className="p-6"
        subtitle="Trace JSON keeps tool evidence visible for project review and debugging."
        title="JSON Trace"
      >
        <details className="mt-5 rounded-lg border border-line bg-slate-50 p-4">
          <summary className="cursor-pointer text-sm font-extrabold text-ink">
            展开 tool_results
          </summary>
          <pre className="mt-4 max-h-80 overflow-auto text-xs font-semibold leading-5 text-slate-700">
            {JSON.stringify(productAdTrace, null, 2)}
          </pre>
        </details>
      </Card>
    </div>
  );
}
