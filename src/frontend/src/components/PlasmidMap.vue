<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'

interface PlasmidFeature {
  name: string
  type: string
  start: number
  end: number
  strand: string
  color?: string
}

interface Props {
  sequence?: string
  features?: PlasmidFeature[]
  name?: string
  length?: number
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 500,
  height: 500,
  features: () => []
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
const hoveredFeature = ref<PlasmidFeature | null>(null)
const selectedFeature = ref<PlasmidFeature | null>(null)

// 特征类型颜色映射
const featureColors: Record<string, string> = {
  promoter: '#FF6B6B',
  terminator: '#4ECDC4',
  CDS: '#45B7D1',
  gene: '#45B7D1',
  origin: '#96CEB4',
  resistance: '#FFEAA7',
  tag: '#DDA0DD',
  MCS: '#FFA500',
  multiple_cloning_site: '#FFA500',
  other: '#CCCCCC'
}

// 计算载体长度
const plasmidLength = computed(() => {
  return props.length || props.sequence?.length || 5000
})

// 绘制质粒图谱
function drawPlasmid() {
  const canvas = canvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = props.width
  const height = props.height
  const centerX = width / 2
  const centerY = height / 2
  const radius = Math.min(width, height) / 2 - 60
    const featureWidth = 25

  // 清空画布
  ctx.clearRect(0, 0, width, height)

  // 绘制背景
  ctx.fillStyle = '#FAFAFA'
  ctx.fillRect(0, 0, width, height)

  // 绘制质粒骨架（环形）
  ctx.beginPath()
  ctx.arc(centerX, centerY, radius - featureWidth / 2, 0, Math.PI * 2)
  ctx.strokeStyle = '#E0E0E0'
  ctx.lineWidth = featureWidth + 10
  ctx.stroke()

  // 绘制刻度
  drawScale(ctx, centerX, centerY, radius + 20, plasmidLength.value)

  // 绘制特征
  props.features.forEach((feature, index) => {
    drawFeature(ctx, centerX, centerY, radius - featureWidth / 2, featureWidth, feature, index)
  })

  // 绘制中心信息
  drawCenterInfo(ctx, centerX, centerY, props.name || 'Plasmid', plasmidLength.value)
}

function drawFeature(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  width: number,
  feature: PlasmidFeature,
  _index: number
) {
  const startAngle = (feature.start / plasmidLength.value) * Math.PI * 2 - Math.PI / 2
  const endAngle = (feature.end / plasmidLength.value) * Math.PI * 2 - Math.PI / 2
  
  const color = feature.color || featureColors[feature.type] || featureColors.other
  const isHovered = hoveredFeature.value === feature
  const isSelected = selectedFeature.value === feature

  // 绘制特征弧
  ctx.beginPath()
  ctx.arc(cx, cy, radius, startAngle, endAngle)
  ctx.lineWidth = isHovered || isSelected ? width + 4 : width
  ctx.strokeStyle = color
  ctx.lineCap = 'butt'
  
  if (isHovered || isSelected) {
    ctx.shadowColor = color
    ctx.shadowBlur = 10
  }
  
  ctx.stroke()
  ctx.shadowBlur = 0

  // 如果是正向链，绘制箭头指示方向
  if (feature.strand === '+' && feature.end - feature.start > 100) {
    const midAngle = ((startAngle + endAngle) / 2)
    const arrowRadius = radius
    const arrowSize = 8
    
    ctx.beginPath()
    const tipX = cx + Math.cos(midAngle) * arrowRadius
    const tipY = cy + Math.sin(midAngle) * arrowRadius
    const baseX1 = cx + Math.cos(midAngle - 0.1) * (arrowRadius - arrowSize)
    const baseY1 = cy + Math.sin(midAngle - 0.1) * (arrowRadius - arrowSize)
    const baseX2 = cx + Math.cos(midAngle + 0.1) * (arrowRadius - arrowSize)
    const baseY2 = cy + Math.sin(midAngle + 0.1) * (arrowRadius - arrowSize)
    
    ctx.moveTo(tipX, tipY)
    ctx.lineTo(baseX1, baseY1)
    ctx.lineTo(baseX2, baseY2)
    ctx.closePath()
    ctx.fillStyle = color
    ctx.fill()
  }
}

function drawScale(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  length: number
) {
  ctx.font = '10px Arial'
  ctx.fillStyle = '#888'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  const majorTicks = 8
  for (let i = 0; i < majorTicks; i++) {
    const angle = (i / majorTicks) * Math.PI * 2 - Math.PI / 2
    const x = cx + Math.cos(angle) * radius
    const y = cy + Math.sin(angle) * radius
    
    // 刻度线
    const innerX = cx + Math.cos(angle) * (radius - 8)
    const innerY = cy + Math.sin(angle) * (radius - 8)
    ctx.beginPath()
    ctx.moveTo(innerX, innerY)
    ctx.lineTo(x, y)
    ctx.strokeStyle = '#AAA'
    ctx.lineWidth = 1
    ctx.stroke()

    // 刻度值
    const labelX = cx + Math.cos(angle) * (radius + 15)
    const labelY = cy + Math.sin(angle) * (radius + 15)
    const value = Math.round((i / majorTicks) * length)
    ctx.fillText(formatNumber(value), labelX, labelY)
  }
}

function drawCenterInfo(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  name: string,
  length: number
) {
  ctx.font = 'bold 14px Arial'
  ctx.fillStyle = '#333'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(name.substring(0, 15), cx, cy - 10)

  ctx.font = '12px Arial'
  ctx.fillStyle = '#666'
  ctx.fillText(formatNumber(length) + ' bp', cx, cy + 10)
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// 鼠标事件处理
function handleMouseMove(event: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return

  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const cx = props.width / 2
  const cy = props.height / 2

  // 计算角度和距离
  const dx = x - cx
  const dy = y - cy
  const distance = Math.sqrt(dx * dx + dy * dy)
  const radius = Math.min(props.width, props.height) / 2 - 60

  // 检查是否在特征环上
  if (distance < radius + 20 && distance > radius - 40) {
    let angle = Math.atan2(dy, dx) + Math.PI / 2
    if (angle < 0) angle += Math.PI * 2
    const position = (angle / (Math.PI * 2)) * plasmidLength.value

    // 查找悬停的特征
    for (const feature of props.features) {
      if (position >= feature.start && position <= feature.end) {
        hoveredFeature.value = feature
        canvas.style.cursor = 'pointer'
        return
      }
    }
  }

  hoveredFeature.value = null
  canvas.style.cursor = 'default'
}

function handleClick(_event: MouseEvent) {
  if (hoveredFeature.value) {
    selectedFeature.value = selectedFeature.value === hoveredFeature.value 
      ? null 
      : hoveredFeature.value
    drawPlasmid()
  }
}

// 监听属性变化
watch(() => [props.features, props.sequence, props.length], drawPlasmid, { deep: true })

onMounted(() => {
  drawPlasmid()
})
</script>

<template>
  <div class="plasmid-map-container">
    <canvas
      ref="canvasRef"
      :width="width"
      :height="height"
      @mousemove="handleMouseMove"
      @click="handleClick"
    />
    
    <!-- 悬停提示 -->
    <div v-if="hoveredFeature" class="feature-tooltip" :style="{ left: '50%', top: '10px' }">
      <div class="tooltip-header">
        <span class="tooltip-type" :style="{ backgroundColor: featureColors[hoveredFeature.type] || '#CCC' }">
          {{ hoveredFeature.type }}
        </span>
        <span class="tooltip-name">{{ hoveredFeature.name }}</span>
      </div>
      <div class="tooltip-details">
        <span>{{ hoveredFeature.start }} - {{ hoveredFeature.end }} bp</span>
        <span>({{ hoveredFeature.end - hoveredFeature.start + 1 }} bp)</span>
      </div>
    </div>

    <!-- 特征图例 -->
    <div class="legend">
      <div v-for="(color, type) in featureColors" :key="type" class="legend-item">
        <span class="legend-color" :style="{ backgroundColor: color }"></span>
        <span class="legend-label">{{ type }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plasmid-map-container {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

canvas {
  border-radius: 8px;
  background: #FAFAFA;
}

.feature-tooltip {
  position: absolute;
  background: white;
  padding: 8px 12px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  pointer-events: none;
  z-index: 10;
  transform: translateX(-50%);
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.tooltip-type {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  color: white;
  font-weight: 500;
}

.tooltip-name {
  font-weight: 600;
  font-size: 13px;
}

.tooltip-details {
  font-size: 11px;
  color: #666;
  display: flex;
  gap: 8px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding: 12px;
  background: #F5F5F5;
  border-radius: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.legend-label {
  font-size: 11px;
  color: #555;
  text-transform: capitalize;
}
</style>
