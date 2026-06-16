export function renderMarkdown(text: string): string {
    if (!text) return ''
    
    let html = text
    
    html = html.replace(/^######\s+(.*)$/gm, '<h6 class="text-sm font-semibold mt-3 mb-1">$1</h6>')
    html = html.replace(/^#####\s+(.*)$/gm, '<h5 class="text-base font-semibold mt-3 mb-1">$1</h5>')
    html = html.replace(/^####\s+(.*)$/gm, '<h4 class="text-base font-semibold mt-4 mb-2">$1</h4>')
    html = html.replace(/^###\s+(.*)$/gm, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
    html = html.replace(/^##\s+(.*)$/gm, '<h2 class="text-xl font-bold mt-5 mb-3">$1</h2>')
    html = html.replace(/^#\s+(.*)$/gm, '<h1 class="text-2xl font-bold mt-6 mb-4">$1</h1>')
    
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
    html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>')
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>')
    html = html.replace(/_(.+?)_/g, '<em>$1</em>')
    html = html.replace(/`([^`]+)`/g, '<code class="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">$1</code>')
    html = html.replace(/~~(.+?)~~/g, '<del>$1</del>')
    
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-muted p-3 rounded-lg text-sm font-mono overflow-x-auto my-3"><code>$1</code></pre>')
    
    html = html.replace(/^\s*[-*+]\s+(.*)$/gm, '<li class="ml-4 list-disc">$1</li>')
    html = html.replace(/^\s*(\d+)\.\s+(.*)$/gm, '<li class="ml-4 list-decimal">$2</li>')
    
    html = html.replace(/^\s*>\s+(.*)$/gm, '<blockquote class="border-l-4 border-primary/30 pl-4 my-3 text-muted-foreground italic">$1</blockquote>')
    
    html = html.replace(/^\s*---\s*$/gm, '<hr class="my-4 border-border" />')
    
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-primary hover:underline">$1</a>')
    
    html = html.replace(/\n\n/g, '</p><p class="my-2">')
    html = '<p class="my-2">' + html + '</p>'
    
    html = html.replace(/(<\/?(ul|ol|li|h1|h2|h3|h4|h5|h6|pre|blockquote|hr)[^>]*>)/g, '</p>$1<p class="my-2">')
    html = html.replace(/<p class="my-2"><\/p>/g, '')
    html = html.replace(/<p class="my-2">\s*<\//g, '</')
    html = html.replace(/<\/li><p class="my-2">/g, '</li>')
    
    html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, '<ul class="list-disc pl-6 my-3 space-y-1">$&</ul>')
    
    return html
}

export function getNoteExcerpt(content: string, maxLength: number = 100): string {
    const plainText = content
        .replace(/[#*_`~\[\]()!>-]/g, '')
        .replace(/\n/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    
    if (plainText.length <= maxLength) return plainText
    return plainText.slice(0, maxLength) + '...'
}
