"use client"

import { motion } from "motion/react"
import { TrendingUp, ShieldAlert, Activity } from "lucide-react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Pie, PieChart, Cell, Tooltip } from "recharts"

import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    ChartConfig,
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent
} from "@/components/ui/chart"

// --- Mock Data ---

const areaChartData = [
    { month: "Jan", deepfakes: 186, authentic: 80, intercepted: 110 },
    { month: "Feb", deepfakes: 305, authentic: 200, intercepted: 250 },
    { month: "Mar", deepfakes: 237, authentic: 120, intercepted: 200 },
    { month: "Apr", deepfakes: 73, authentic: 190, intercepted: 65 },
    { month: "May", deepfakes: 209, authentic: 130, intercepted: 180 },
    { month: "Jun", deepfakes: 214, authentic: 140, intercepted: 205 },
]

const areaChartConfig = {
    deepfakes: {
        label: "Total Deepfakes",
        color: "hsl(var(--chart-1))",
    },
    authentic: {
        label: "Authentic Media",
        color: "hsl(var(--chart-2))",
    },
    intercepted: {
        label: "Intercepted",
        color: "hsl(var(--chart-3))",
    }
} satisfies ChartConfig

const radarChartData = [
    { subject: "Audio", forensics: 120, osint: 110, fullMark: 150 },
    { subject: "Video", forensics: 98, osint: 130, fullMark: 150 },
    { subject: "Text", forensics: 86, osint: 130, fullMark: 150 },
    { subject: "Network", forensics: 99, osint: 100, fullMark: 150 },
    { subject: "Metadata", forensics: 85, osint: 90, fullMark: 150 },
    { subject: "Behavior", forensics: 65, osint: 85, fullMark: 150 },
]

const radarChartConfig = {
    forensics: {
        label: "Forensics Engine",
        color: "hsl(var(--chart-1))",
    },
    osint: {
        label: "OSINT Intel",
        color: "hsl(var(--chart-2))",
    },
} satisfies ChartConfig

const pieChartData = [
    { name: "Face Swap", value: 400, color: "#EF4444" },
    { name: "Voice Clone", value: 300, color: "#F97316" },
    { name: "Synthetic Text", value: 300, color: "#3B82F6" },
    { name: "Lip Sync", value: 200, color: "#D4FF12" },
]

const pieChartConfig = {
    value: {
        label: "Threats",
    }
} satisfies ChartConfig


export function InteractiveCharts() {
    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full">
            {/* Area Chart: Historical Trends */}
            <motion.div
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6 }}
                className="col-span-1 lg:col-span-2"
            >
                <Card className="bg-card backdrop-blur-xl border-border text-foreground overflow-hidden relative liquid-glass">
                    <div className="absolute top-[-100px] left-[-100px] w-64 h-64 bg-[#6366F1]/10 rounded-full blur-[100px] pointer-events-none" />
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Activity className="w-5 h-5 text-[#6366F1]" />
                            六个月拦截趋势分析 (6-Month Interception Trends)
                        </CardTitle>
                        <CardDescription className="text-[#9CA3AF]">
                            Showing detection volume and interception rates over the last 6 months
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <ChartContainer config={areaChartConfig} className="h-[300px] w-full">
                            <AreaChart
                                accessibilityLayer
                                data={areaChartData}
                                margin={{
                                    left: 12,
                                    right: 12,
                                }}
                            >
                                <defs>
                                    <linearGradient id="fillDeepfakes" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#EF4444" stopOpacity={0.4} />
                                        <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="fillAuthentic" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#6366F1" stopOpacity={0.4} />
                                        <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid vertical={false} stroke="#374151" strokeDasharray="3 3" />
                                <XAxis
                                    dataKey="month"
                                    tickLine={false}
                                    axisLine={false}
                                    tickMargin={8}
                                    tickFormatter={(value) => value.slice(0, 3)}
                                    stroke="#9CA3AF"
                                />
                                <YAxis stroke="#9CA3AF" tickLine={false} axisLine={false} />
                                <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
                                <Area
                                    dataKey="authentic"
                                    type="monotone"
                                    fill="url(#fillAuthentic)"
                                    fillOpacity={1}
                                    stroke="#6366F1"
                                    strokeWidth={2}
                                    stackId="1"
                                />
                                <Area
                                    dataKey="deepfakes"
                                    type="monotone"
                                    fill="url(#fillDeepfakes)"
                                    fillOpacity={1}
                                    stroke="#EF4444"
                                    strokeWidth={2}
                                    stackId="2"
                                />
                                <Area
                                    dataKey="intercepted"
                                    type="monotone"
                                    fill="transparent"
                                    stroke="#D4FF12"
                                    strokeWidth={2}
                                    strokeDasharray="5 5"
                                />
                            </AreaChart>
                        </ChartContainer>
                    </CardContent>
                    <CardFooter>
                        <div className="flex w-full items-start gap-2 text-sm">
                            <div className="grid gap-2">
                                <div className="flex items-center gap-2 font-medium leading-none text-[#D4FF12]">
                                    Interception rate up by 15.2% this month <TrendingUp className="h-4 w-4" />
                                </div>
                                <div className="flex items-center gap-2 leading-none text-[#9CA3AF]">
                                    Data aggregated from global Threat Intelligence feeds
                                </div>
                            </div>
                        </div>
                    </CardFooter>
                </Card>
            </motion.div>

            {/* Radar Chart: Modality Performance */}
            <motion.div
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: 0.2 }}
            >
                <Card className="bg-card backdrop-blur-xl border-border text-foreground h-full relative overflow-hidden liquid-glass">
                    <div className="absolute bottom-[-100px] right-[-100px] w-48 h-48 bg-[#D4FF12]/10 rounded-full blur-[80px] pointer-events-none" />
                    <CardHeader className="items-center pb-4">
                        <CardTitle>多维防线强度模型 (Defense Modality Matrix)</CardTitle>
                        <CardDescription className="text-[#9CA3AF]">
                            Forensics Engine vs OSINT Intelligence
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="pb-0">
                        <ChartContainer
                            config={radarChartConfig}
                            className="mx-auto aspect-square max-h-[300px]"
                        >
                            <RadarChart data={radarChartData}>
                                <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
                                <PolarGrid stroke="#4B5563" />
                                <PolarAngleAxis dataKey="subject" stroke="#D1D5DB" tick={{ fill: "#D1D5DB", fontSize: 12 }} />
                                <PolarRadiusAxis angle={30} domain={[0, 150]} tick={false} axisLine={false} />
                                <Radar
                                    name="Forensics Engine"
                                    dataKey="forensics"
                                    stroke="#6366F1"
                                    fill="#6366F1"
                                    fillOpacity={0.4}
                                />
                                <Radar
                                    name="OSINT Intel"
                                    dataKey="osint"
                                    stroke="#D4FF12"
                                    fill="#D4FF12"
                                    fillOpacity={0.4}
                                />
                                <ChartLegend className="mt-4" content={<ChartLegendContent />} />
                            </RadarChart>
                        </ChartContainer>
                    </CardContent>
                </Card>
            </motion.div>

            {/* Donut Chart: Live Threat Distribution */}
            <motion.div
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: 0.4 }}
            >
                <Card className="bg-card backdrop-blur-xl border-border text-foreground h-full relative overflow-hidden flex flex-col liquid-glass">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 bg-red-500/10 rounded-full blur-[80px] pointer-events-none" />
                    <CardHeader className="items-center pb-0">
                        <CardTitle className="flex items-center gap-2">
                            <ShieldAlert className="w-5 h-5 text-red-500" />
                            实时活跃伪造类型 (Active Fakes Distribution)
                        </CardTitle>
                        <CardDescription className="text-[#9CA3AF]">Live updating past 24 hours</CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 pb-0 mt-4">
                        <ChartContainer
                            config={pieChartConfig}
                            className="mx-auto aspect-square max-h-[300px] pb-0"
                        >
                            <PieChart>
                                <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                                <Pie
                                    data={pieChartData}
                                    dataKey="value"
                                    nameKey="name"
                                    innerRadius={60}
                                    outerRadius={100}
                                    strokeWidth={5}
                                    stroke="#1F2937"
                                    activeIndex={0}
                                    activeShape={({ outerRadius = 0, ...props }: any) => (
                                        <g>
                                            <circle cx={props.cx} cy={props.cy} r={outerRadius + 10} fill={props.fill} opacity={0.2} className="animate-pulse" />
                                            <path d={props.sector} fill={props.fill} />
                                        </g>
                                    )}
                                >
                                    {pieChartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                            </PieChart>
                        </ChartContainer>
                    </CardContent>
                    <CardFooter className="flex-col gap-2 text-sm mt-4">
                        <div className="flex items-center gap-2 font-medium leading-none text-foreground">
                            Face Swap attacks dominate at 33% <TrendingUp className="h-4 w-4 text-red-500" />
                        </div>
                        <div className="leading-none text-muted-foreground text-[#9CA3AF]">
                            Requires immediate resource allocation to Video Forensics.
                        </div>
                    </CardFooter>
                </Card>
            </motion.div>
        </div>
    )
}
