export interface StockTag {
    id: number
    name: string
    color: string
    description?: string
    stock_count?: number
    created_at: string
    updated_at: string
}

export interface StockNote {
    id: number
    symbol: string
    stock_name?: string
    title?: string
    content: string
    created_at: string
    updated_at: string
}

export interface StockTagNoteAggregate {
    symbol: string
    stock_name?: string
    tags: StockTag[]
    notes: StockNote[]
}

export interface TagListResponse {
    total: number
    items: StockTag[]
}

export interface NoteListResponse {
    total: number
    items: StockNote[]
}
