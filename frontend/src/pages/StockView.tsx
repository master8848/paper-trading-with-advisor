import { useParams, Link, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  IconExternalLink,
  IconArrowLeft,
  IconChartLine,
  IconBuildingBank,
  IconTrendingUp,
} from "@tabler/icons-react"

type ExternalLink = {
  label: string
  href: string
  description: string
  variant?: "default" | "secondary" | "outline"
}

function buildExternalLinks(symbol: string): ExternalLink[] {
  const upper = symbol.toUpperCase()
  const encoded = encodeURIComponent(upper)
  return [
    {
      label: "Screener.in",
      href: `https://www.screener.in/company/${encoded}/`,
      description: "Fundamentals, ratios & annual reports",
      variant: "default",
    },
    {
      label: "NSE India",
      href: `https://www.nseindia.com/get-quotes/equity?symbol=${encoded}`,
      description: "Official NSE quote & announcements",
      variant: "secondary",
    },
    {
      label: "BSE India",
      href: `https://www.bseindia.com/stock-share-price/${encoded}/`,
      description: "BSE price, corporate actions",
      variant: "secondary",
    },
    {
      label: "TradingView",
      href: `https://www.tradingview.com/symbols/NSE-${encoded}/`,
      description: "Advanced chart, TA & community ideas",
      variant: "outline",
    },
  ]
}

export default function StockView() {
  const { symbol = "" } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const upperSymbol = symbol.toUpperCase()

  const { data: stockData, isLoading } = useQuery({
    queryKey: ["stock-detail", upperSymbol],
    queryFn: () => api<any>(`/stock-exchange/${upperSymbol}`),
    enabled: !!upperSymbol,
    retry: false,
    staleTime: Infinity,
  })

  const { data: ourRecord } = useQuery({
    queryKey: ["stock-record", upperSymbol],
    queryFn: () =>
      api<any>(`/stocks?load=true`)
        .then((r: any) => {
          // backend returns array in r or r.data
          const arr = Array.isArray(r) ? r : r?.data || []
          return arr.find((s: { stockName: string }) => s.stockName?.toUpperCase() === upperSymbol)
        })
        .catch(() => null),
    enabled: !!upperSymbol,
    staleTime: Infinity,
  })

  const externalLinks = buildExternalLinks(upperSymbol)

  // TradingView widget src - uses symbol NSE:SYMBOL
  const tradingViewSrc = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=NSE%3A${encodeURIComponent(
    upperSymbol
  )}&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=%5B%5D&theme=light&style=1&timezone=Asia%2FKolkata&withdateranges=1&hideideas=1&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=NSE%3A${encodeURIComponent(
    upperSymbol
  )}`

  return (
    <div className="container mx-auto max-w-6xl px-4 py-6 space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="gap-2">
        <IconArrowLeft size={16} />
        Back
      </Button>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <IconChartLine className="text-primary" size={28} />
            {upperSymbol}
          </h1>
          <p className="text-muted-foreground text-sm">Detailed view • Price chart, fundamentals & external research</p>
        </div>
        <div className="text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <IconTrendingUp size={16} /> NSE Symbol
          </span>
        </div>
      </div>

      {/* External links - prominent "paid redirecting is best" */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background shadow-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <IconExternalLink size={20} className="text-primary" />
            Research & Trade – External Links
          </CardTitle>
          <CardDescription>
            Open the most trusted platforms in a new tab. These are the best destinations for deep research and live trading.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {externalLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="group"
              >
                <Button
                  variant={link.variant ?? "outline"}
                  className="w-full h-auto flex flex-col items-start gap-1 p-4 text-left whitespace-normal shadow-sm group-hover:shadow-md transition-all group-hover:-translate-y-0.5"
                >
                  <span className="flex w-full items-center justify-between font-semibold">
                    {link.label}
                    <IconExternalLink size={16} className="shrink-0 opacity-70 group-hover:opacity-100" />
                  </span>
                  <span className="text-xs font-normal opacity-80 line-clamp-2">{link.description}</span>
                  <span className="text-[10px] opacity-60 break-all">{link.href}</span>
                </Button>
              </a>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Tip: Right-click → “Open link in new tab” or click to redirect instantly. We never proxy paid data – we send you to the source.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Chart */}
        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <IconChartLine size={18} />
              Price Chart (TradingView)
            </CardTitle>
            <CardDescription>Live TradingView widget for NSE:{upperSymbol}</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="relative w-full h-[420px] bg-muted">
              <iframe
                title={`TradingView chart for ${upperSymbol}`}
                src={tradingViewSrc}
                className="w-full h-full border-0"
                loading="lazy"
              />
              <div className="pointer-events-none absolute inset-0 border-t" />
            </div>
            <div className="p-4 text-xs text-muted-foreground flex justify-between">
              <span>Powered by TradingView</span>
              <a
                href={`https://www.tradingview.com/symbols/NSE-${upperSymbol}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 hover:underline text-primary"
              >
                Open full chart <IconExternalLink size={12} />
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Fundamentals */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <IconBuildingBank size={18} />
                Fundamentals
              </CardTitle>
              <CardDescription>Snapshot from NSE + your portfolio</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Loading live quote…</p>
              ) : stockData ? (
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <div className="space-y-1">
                    <dt className="text-muted-foreground text-xs uppercase tracking-wide">Last Traded Price</dt>
                    <dd className="font-semibold text-lg">₹{stockData.lastTradedPrice ?? stockData.lastPrice ?? "—"}</dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-muted-foreground text-xs uppercase tracking-wide">Day Change</dt>
                    <dd className="font-medium">{stockData.change ?? stockData.pChange ?? "—"}</dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-muted-foreground text-xs uppercase tracking-wide">52W Low</dt>
                    <dd className="font-medium">₹{stockData.fiftyTwoWeekLow ?? "—"}</dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-muted-foreground text-xs uppercase tracking-wide">52W High</dt>
                    <dd className="font-medium">₹{stockData.fiftyTwoWeekHigh ?? "—"}</dd>
                  </div>
                  {stockData.dayHigh && (
                    <div className="space-y-1">
                      <dt className="text-muted-foreground text-xs uppercase tracking-wide">Day High</dt>
                      <dd>₹{stockData.dayHigh}</dd>
                    </div>
                  )}
                  {stockData.dayLow && (
                    <div className="space-y-1">
                      <dt className="text-muted-foreground text-xs uppercase tracking-wide">Day Low</dt>
                      <dd>₹{stockData.dayLow}</dd>
                    </div>
                  )}
                  <div className="col-span-2 pt-2 border-t">
                    <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-32">
                      {JSON.stringify(stockData, null, 2)}
                    </pre>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground">No live data. Try external links above for live quote.</p>
              )}

              {ourRecord && (
                <div className="pt-4 border-t space-y-2">
                  <h4 className="font-medium text-sm">Your record</h4>
                  <dl className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <dt className="text-muted-foreground text-xs">Buy Price</dt>
                      <dd>₹{ourRecord.price}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs">Quantity</dt>
                      <dd>{ourRecord.quantity}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs">Type</dt>
                      <dd>{ourRecord.type}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs">Total</dt>
                      <dd>₹{ourRecord.total}</dd>
                    </div>
                  </dl>
                  {ourRecord.message && <p className="text-xs bg-muted p-2 rounded">{ourRecord.message}</p>}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-muted/30">
            <CardContent className="pt-6 text-xs text-muted-foreground space-y-2">
              <p className="font-medium text-foreground">Why external links?</p>
              <p>
                We believe <span className="font-semibold">paid redirecting is best</span> — instead of scraping or paywalling data, we
                redirect you to the authoritative source (Screener, NSE, BSE, TradingView) where you get the freshest, licensed data and can
                trade directly.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
