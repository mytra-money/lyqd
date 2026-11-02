<template>
  <div>
    <PageHeader
      title="Scheme catalogue"
      subtitle="Eligible schemes for investment instructions. Catalogue is maintained here."
    >
      <Button variant="outline" :loading="seeding" @click="seedDefaults">Ensure defaults</Button>
      <Button variant="solid" @click="openNew">Add scheme</Button>
    </PageHeader>

    <div class="grid gap-3 md:grid-cols-2">
      <div v-for="row in list.data || []" :key="row.name" class="rounded-md border border-gray-200 bg-white p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-base font-semibold text-gray-900">{{ row.scheme_name }}</div>
            <div class="mt-1 font-mono text-xs text-gray-500">{{ row.isin }}</div>
            <div class="mt-2 text-sm text-gray-600">{{ row.amc }} · {{ row.category }}</div>
          </div>
          <div class="flex flex-col items-end gap-1">
            <Badge v-if="row.is_default">Default</Badge>
            <Badge :theme="row.is_active ? 'blue' : 'gray'">{{
              row.is_active ? 'Active' : 'Inactive'
            }}</Badge>
          </div>
        </div>
        <p v-if="row.description" class="mt-3 text-sm text-gray-500">{{ row.description }}</p>
      </div>
    </div>

    <Dialog v-model="show" :options="{ title: 'New scheme' }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl v-model="form.scheme_name" label="Scheme name" />
          <FormControl v-model="form.isin" label="ISIN" />
          <FormControl v-model="form.amc" label="AMC" />
          <FormControl
            v-model="form.category"
            type="select"
            label="Category"
            :options="['Liquid', 'Overnight', 'Ultra Short', 'Other']"
          />
          <FormControl v-model="form.description" type="textarea" label="Description" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
        <Button variant="outline" @click="show = false">Cancel</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { call, createListResource, toast } from 'frappe-ui'
import PageHeader from '@/components/PageHeader.vue'

const show = ref(false)
const saving = ref(false)
const seeding = ref(false)
const form = reactive({
  scheme_name: '',
  isin: '',
  amc: '',
  category: 'Liquid',
  description: '',
})

const list = createListResource({
  doctype: 'LYQD Scheme',
  fields: [
    'name',
    'scheme_name',
    'isin',
    'amc',
    'category',
    'is_active',
    'is_default',
    'description',
  ],
  orderBy: 'is_default desc, scheme_name asc',
  auto: true,
})

onMounted(() => list.reload())

function openNew() {
  Object.assign(form, {
    scheme_name: '',
    isin: '',
    amc: '',
    category: 'Liquid',
    description: '',
  })
  show.value = true
}

async function seedDefaults() {
  seeding.value = true
  try {
    await call('lyqd.api.spa.ensure_default_schemes')
    toast.success('Default schemes ready')
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Could not seed schemes')
  } finally {
    seeding.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await call('frappe.client.insert', {
      doc: {
        doctype: 'LYQD Scheme',
        ...form,
        is_active: 1,
      },
    })
    toast.success('Scheme saved')
    show.value = false
    list.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || 'Save failed')
  } finally {
    saving.value = false
  }
}
</script>
