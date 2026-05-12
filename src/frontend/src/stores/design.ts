import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DesignRequest, DesignResult } from '@/types'
import {
  submitDesign as apiSubmitDesign,
  getDesign as apiGetDesign,
  submitBatchDesign as apiSubmitBatch,
  getBatchProgress as apiGetBatchProgress,
  downloadBatchResults as apiDownloadBatch,
  getBatchReport as apiGetBatchReport
} from '@/api'

export const useDesignStore = defineStore('design', () => {
  const currentDesign = ref<DesignResult | null>(null)
  const batchProgress = ref<any>(null)
  const batchReport = ref<any>(null)
  const loading = ref(false)
  const error = ref('')

  async function submitDesign(request: DesignRequest): Promise<string> {
    loading.value = true
    error.value = ''
    try {
      const result = await apiSubmitDesign(request)
      return result.design_id
    } catch (e: any) {
      error.value = e.message || '提交失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchDesign(designId: string): Promise<DesignResult> {
    try {
      const data = await apiGetDesign(designId)
      currentDesign.value = data
      return data
    } catch (e: any) {
      error.value = e.message || '获取设计失败'
      throw e
    }
  }

  async function submitBatch(request: any): Promise<string> {
    loading.value = true
    error.value = ''
    try {
      const result = await apiSubmitBatch(request)
      return result.batch_id
    } catch (e: any) {
      error.value = e.message || '批量提交失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function pollBatchProgress(batchId: string): Promise<any> {
    try {
      const data = await apiGetBatchProgress(batchId)
      batchProgress.value = data
      // 如果完成，自动获取报告
      if (data.status === 'completed' && !batchReport.value) {
        fetchBatchReport(batchId)
      }
      return data
    } catch (e: any) {
      console.error('Poll batch progress failed:', e)
      throw e
    }
  }

  async function downloadBatchResults(batchId: string): Promise<void> {
    await apiDownloadBatch(batchId)
  }

  async function fetchBatchReport(batchId: string): Promise<any> {
    try {
      const data = await apiGetBatchReport(batchId)
      batchReport.value = data
      return data
    } catch (e: any) {
      console.error('Fetch batch report failed:', e)
      return null
    }
  }

  function resetBatch() {
    batchProgress.value = null
    batchReport.value = null
    error.value = ''
  }

  return {
    currentDesign,
    batchProgress,
    batchReport,
    loading,
    error,
    submitDesign,
    fetchDesign,
    submitBatch,
    pollBatchProgress,
    downloadBatchResults,
    fetchBatchReport,
    resetBatch
  }
})
