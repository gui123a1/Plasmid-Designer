import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { VectorInfo } from '@/types'
import {
  getVectors as apiGetVectors,
  searchNcbi as apiSearchNcbi,
  previewNcbi as apiPreviewNcbi,
  importFromNcbiId as apiImportFromNcbiId,
  uploadVectorFile as apiUploadVectorFile,
  deleteVector as apiDeleteVector,
  updateVector as apiUpdateVector,
  batchImportVectors as apiBatchImportVectors
} from '@/api'

export const useVectorsStore = defineStore('vectors', () => {
  const vectors = ref<VectorInfo[]>([])
  const loading = ref(false)
  const filterType = ref('')
  const filterHost = ref('')
  const ncbiSearchResults = ref<any[]>([])
  const ncbiSearching = ref(false)
  const ncbiQuery = ref('')

  async function loadVectors(type?: string, host?: string) {
    loading.value = true
    try {
      vectors.value = await apiGetVectors(type || filterType.value, host || filterHost.value)
    } catch (e) {
      console.error('Failed to load vectors:', e)
    } finally {
      loading.value = false
    }
  }

  async function searchNcbi(query: string, limit: number = 10) {
    ncbiSearching.value = true
    ncbiQuery.value = query
    try {
      const result = await apiSearchNcbi(query, limit)
      ncbiSearchResults.value = result.results || []
      return result
    } catch (e: any) {
      console.error('NCBI search failed:', e)
      ncbiSearchResults.value = []
      throw e
    } finally {
      ncbiSearching.value = false
    }
  }

  async function previewNcbi(seqId: string) {
    return await apiPreviewNcbi(seqId)
  }

  async function importFromNcbiId(seqId: string) {
    const result = await apiImportFromNcbiId(seqId)
    await loadVectors()
    return result
  }

  async function uploadVector(file: File) {
    const result = await apiUploadVectorFile(file)
    await loadVectors()
    return result
  }

  async function removeVector(vectorId: string) {
    await apiDeleteVector(vectorId)
    await loadVectors()
  }

  async function editVector(vectorId: string, data: {
    name?: string; description?: string; vector_type?: string;
    host?: string[]; antibiotic_resistance?: string[]; copy_number?: string
  }) {
    const result = await apiUpdateVector(vectorId, data)
    await loadVectors()
    return result
  }

  async function batchImport(ncbiIds: string[], filePaths: string[] = []) {
    const result = await apiBatchImportVectors(ncbiIds, filePaths)
    await loadVectors()
    return result
  }

  return {
    vectors,
    loading,
    filterType,
    filterHost,
    ncbiSearchResults,
    ncbiSearching,
    ncbiQuery,
    loadVectors,
    searchNcbi,
    previewNcbi,
    importFromNcbiId,
    uploadVector,
    removeVector,
    editVector,
    batchImport
  }
})
