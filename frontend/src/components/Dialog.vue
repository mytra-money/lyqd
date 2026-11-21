<script setup>
/**
 * Compat layer for frappe-ui 0.1 Dialog API on top of 1.x.
 * Maps `:options="{ title, size }"`, `#body-content`, `#body-header`,
 * and `disable-outside-click-to-close` onto the 1.x Dialog.
 */
import { computed, useAttrs, useSlots } from 'vue'
import { Dialog as FuiDialog } from 'frappe-ui'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  modelValue: { type: Boolean, default: undefined },
  open: { type: Boolean, default: undefined },
  options: { type: Object, default: null },
  title: { type: String, default: undefined },
  size: { type: String, default: undefined },
  message: { type: String, default: undefined },
  dismissible: { type: Boolean, default: undefined },
  /** Legacy 0.1 prop — inverted to `dismissible`. */
  disableOutsideClickToClose: { type: Boolean, default: false },
  showCloseButton: { type: Boolean, default: true },
  bare: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'update:open', 'close', 'after-leave'])

const attrs = useAttrs()
const slots = useSlots()

const isOpen = computed({
  get() {
    if (props.open !== undefined) return props.open
    return !!props.modelValue
  },
  set(value) {
    emit('update:modelValue', value)
    emit('update:open', value)
    if (!value) emit('close')
  },
})

const resolvedTitle = computed(() => props.title ?? props.options?.title)
const resolvedSize = computed(() => props.size ?? props.options?.size ?? 'lg')
const resolvedMessage = computed(() => props.message ?? props.options?.message)
const resolvedDismissible = computed(() => {
  if (props.dismissible !== undefined) return props.dismissible
  if (props.disableOutsideClickToClose) return false
  if (props.options?.disableOutsideClickToClose) return false
  return true
})

const hasBodyHeader = computed(() => !!slots['body-header'] || !!slots.title)
</script>

<template>
  <FuiDialog
    v-model="isOpen"
    :title="resolvedTitle"
    :size="resolvedSize"
    :message="slots['body-content'] || slots.default ? undefined : resolvedMessage"
    :dismissible="resolvedDismissible"
    :show-close-button="showCloseButton"
    :bare="bare"
    v-bind="attrs"
    @after-leave="emit('after-leave')"
  >
    <template v-if="hasBodyHeader" #title="slotProps">
      <slot name="body-header" v-bind="slotProps" />
      <slot name="title" v-bind="slotProps" />
    </template>

    <slot name="body-content" :close="() => (isOpen = false)" />
    <slot :close="() => (isOpen = false)" />

    <template v-if="slots.actions" #actions="slotProps">
      <div class="flex flex-row-reverse flex-wrap gap-2">
        <slot name="actions" v-bind="slotProps" />
      </div>
    </template>
  </FuiDialog>
</template>
