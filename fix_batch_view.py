"""Fix BatchDesignView.vue - rewrite script section to fix duplicate functions"""

import os

vue_path = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'frontend', 'src', 'views', 'BatchDesignView.vue'
)
vue_path = os.path.normpath(vue_path)

# Read the current file
with open(vue_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The script section has duplicate handleDownloadBatch and fetchBatchReport functions
# and the getProgressColor function is broken with nested async functions
# We need to replace the entire <script setup> section

new_script = '''<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { VectorInfo, CodonTable } from '@/types'
import { submitBatchDesign, getBatchProgress, downloadBatchResults, getBatchReport, getVectors, getCodonTables } from '@/api'

const router = useRouter()

// 批量序列输入
const sequencesText = ref('')
const sequenceNames = ref<string[]>([])
const sequenceType = ref<'amino_acid' | 'dna'>('amino_acid')

// 设计参数
const vectorId = ref('pET-28a')
const cloningMethod = ref<'gibson' | 'golden_gate' | 'restriction' | 'gene_synthesis'>('gibson')
const protocolLanguage = ref<'zh' | 'en'>('zh')
const optimizeCodons = ref(true)
const targetSpecies = ref('ecoli')
const gcMin = ref(40)
const gcMax = ref(60)

// 全基因合成参数
const oligoLength = ref(60)
const overlapLength = ref(20)

// 任务状态
const isSubmitting = ref(false)
// 动态选项
const availableVectors = ref<VectorInfo[]>([])
const codonTables = ref<CodonTable[]>([])

const batchId = ref('')
const progress = ref<any>(null)
const error = ref('')
const batchReport = ref<any>(null)

// 解析输入的序列
const parsedSequences = computed(() => {
  const lines = sequencesText.value.split(/\\n---+\\n|\\n\\n+/).filter(s => s.trim())
  return lines.map(s => s.trim())
})

const sequenceCount = computed(() => parsedSequences.value.length)

// 批量设计轮询
let pollInterval: number | null = null

async function startPolling(id: string) {
  batchId.value = id

  const poll = async () => {
    try {
      const data = await getBatchProgress(id)
      progress.value = data

      if (data.status === 'completed') {
        fetchBatchReport()
        if (pollInterval) {
          clearInterval(pollInterval)
          pollInterval = null
        }
      }
    } catch (e: any) {
      console.error('Poll error:', e)
    }
  }

  poll()
  pollInterval = window.setInterval(poll, 2000)
}

async function handleSubmit() {
  if (parsedSequences.value.length === 0) {
    error.value = '请输入至少一个序列'
    return
  }

  isSubmitting.value = true
  error.value = ''

  try {
    const result = await submitBatchDesign({
      sequences: parsedSequences.value,
      sequence_names: sequenceNames.value.length > 0 ? sequenceNames.value : undefined,
      sequence_type: sequenceType.value,
      vector_id: vectorId.value,
      cloning_method: cloningMethod.value,
      optimize_codons: optimizeCodons.value,
      target_species: targetSpecies.value,
      gc_min: gcMin.value,
      gc_max: gcMax.value,
      protocol_language: protocolLanguage.value,
      oligo_length: oligoLength.value,
      overlap_length: overlapLength.value,
    })

    startPolling(result.batch_id)
  } catch (e: any) {
    error.value = e.message || '提交失败'
    isSubmitting.value = false
  }
}

onMounted(async () => {
  try { availableVectors.value = await getVectors() } catch (e) { console.warn('Failed to load vectors:', e) }
  try { codonTables.value = await getCodonTables() } catch (e) { console.warn('Failed to load codon tables:', e) }
})

function loadExamples() {
  sequencesText.value = `MKVLWAALLTFLGCAATSGSQAPDRRNRLALASLLRLQGVSSVQIRCRDSDMNADADATIRR\\n---\\nMGVSGAVPKLFVGKTLYFSVFCFVCCFQVVSLSYAYVTLPIAVMVVCTFQQSRQGAAKIF\\n---\\nMNSLWNSTSSSFFRQIFQSIYLCLLGISSVLSQVYILSSQQNKVFQKAFYYSLLKTFQG`
  sequenceType.value = 'amino_acid'
}

function viewResult(designId: string) {
  router.push(`/result/${designId}`)
}

function getProgressColor(): string {
  if (!progress.value) return '#E0E0E0'
  if (progress.value.status === 'completed') return '#10B981'
  if (progress.value.failed > 0) return '#EF4444'
  return '#4F46E5'
}

async function handleDownloadBatch() {
  try {
    await downloadBatchResults(batchId.value)
  } catch (e: any) {
    error.value = '下载失败: ' + (e.message || '未知错误')
  }
}

async function fetchBatchReport() {
  try {
    batchReport.value = await getBatchReport(batchId.value)
  } catch (e) {
    console.warn('Failed to fetch batch report:', e)
  }
}
</script>'''

# Find the template section start
template_start = content.find('<template>')
if template_start == -1:
    print("ERROR: <template> not found")
    exit(1)

# Get the template + style sections (from <template> to end)
template_and_style = content[template_start:]

# Reconstruct the file
new_content = new_script + '\n\n' + template_and_style

with open(vue_path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(new_content)

print(f"Fixed BatchDesignView.vue ({len(new_content)} chars)")
print("Removed duplicate handleDownloadBatch/fetchBatchReport functions")
print("Fixed getProgressColor function (was broken with nested async functions)")
