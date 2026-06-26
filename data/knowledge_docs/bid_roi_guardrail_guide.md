# Bid ROI Guardrail Guide

ROI 守护用于防止商品级广告在加价后获得更多点击但利润或成交效率不足。PCVR * price 可以近似估计单次点击预期成交额，PCVR * price * margin_rate 可以估计单次点击预期毛利。

max_cpc_by_revenue_roi = pcvr * price / target_roi。若考虑毛利，max_cpc_by_profit_roi = pcvr * price * margin_rate / target_roi。推荐 CPC 区间应低于收入 ROI 上限，并结合毛利、安全折扣和退款率风险调整。

当加价后 ROI 低于目标阈值时，应降低出价或进入智能调价保护。当历史 ROI 低于目标 ROI、退款率偏高或评分偏低时，应使用 conservative 策略，并先做小流量 A/B test。
