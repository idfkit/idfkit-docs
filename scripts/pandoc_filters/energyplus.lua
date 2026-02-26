-- Pandoc Lua filter for EnergyPlus documentation
--
-- Handles:
-- 1. Table -> pipe-table markdown (longtable, tabular)
-- 2. CodeBlock -> fenced code blocks with language class
-- 3. BlockQuote -> admonition conversion (from callout environment)
-- 4. Image path resolution (media/ relative references)
-- 5. Figure -> caption preservation and label anchors
-- 6. Link -> intercept Pandoc's \ref{}/\eqref{} for cross-reference resolution
-- 7. Math -> fix \textsubscript/\textsuperscript in math mode
-- 8. Para -> split DisplayMath into standalone blocks with equation numbering
-- 9. Cross-reference handling via label index
-- 10. Definition list formatting for wherelist remnants

-- Convert Table elements to pipe-table markdown for proper rendering.
-- Pandoc's default simple-table output wrapped in ::: divs is not supported
-- by Zensical. We serialize tables as standard pipe tables instead.
function Table(el)
    local function cell_to_text(cell)
        local doc = pandoc.Pandoc(cell.contents)
        local text = pandoc.write(doc, "markdown")
        -- Normalize non-breaking spaces to regular spaces (LaTeX ~ produces
        -- bytes that become invalid UTF-8 when assembled into pipe tables)
        text = text:gsub("\xc2\xa0", " ")  -- UTF-8 non-breaking space
        text = text:gsub("\xa0", " ")       -- bare Latin-1 non-breaking space
        -- Trim trailing whitespace/newlines
        text = text:gsub("%s+$", "")
        -- Collapse newlines to spaces (pipe tables need single-line cells)
        text = text:gsub("\n", " ")
        -- Escape pipe characters in content
        text = text:gsub("|", "\\|")
        return text
    end

    local lines = {}
    local num_cols = #el.colspecs

    -- Extract header rows
    local header_cells = {}
    if el.head and el.head.rows then
        for _, row in ipairs(el.head.rows) do
            local cells = {}
            for _, cell in ipairs(row.cells) do
                table.insert(cells, cell_to_text(cell))
            end
            if #cells > 0 then
                header_cells = cells
            end
        end
    end

    -- Fall back to body rows for column count
    if num_cols == 0 then
        num_cols = #header_cells
    end
    if num_cols == 0 then
        for _, body in ipairs(el.bodies) do
            for _, row in ipairs(body.body) do
                num_cols = #row.cells
                break
            end
            if num_cols > 0 then break end
        end
    end

    if num_cols == 0 then
        return el  -- Can't determine column count, leave as-is
    end

    -- Header row
    if #header_cells > 0 then
        table.insert(lines, "| " .. table.concat(header_cells, " | ") .. " |")
    else
        local empty = {}
        for i = 1, num_cols do table.insert(empty, " ") end
        table.insert(lines, "| " .. table.concat(empty, " | ") .. " |")
    end

    -- Separator row
    local seps = {}
    for i = 1, num_cols do
        table.insert(seps, "---")
    end
    table.insert(lines, "| " .. table.concat(seps, " | ") .. " |")

    -- Body rows
    for _, body in ipairs(el.bodies) do
        for _, row in ipairs(body.body) do
            local cells = {}
            for _, cell in ipairs(row.cells) do
                table.insert(cells, cell_to_text(cell))
            end
            while #cells < num_cols do
                table.insert(cells, "")
            end
            table.insert(lines, "| " .. table.concat(cells, " | ") .. " |")
        end
    end

    -- Caption
    local caption_text = ""
    if el.caption and el.caption.long and #el.caption.long > 0 then
        local cap_doc = pandoc.Pandoc(el.caption.long)
        caption_text = pandoc.write(cap_doc, "markdown"):gsub("%s+$", "")
    end
    if caption_text ~= "" then
        table.insert(lines, "")
        table.insert(lines, "*Table: " .. caption_text .. "*")
    end

    return pandoc.RawBlock("markdown", table.concat(lines, "\n"))
end

-- Tag code blocks (from lstlisting/verbatim) so Pandoc emits fenced blocks.
-- Nearly all code in EnergyPlus docs is IDF; the class also enables future
-- syntax highlighting.
function CodeBlock(el)
    if #el.classes == 0 then
        table.insert(el.classes, "idf")
    end
    return el
end

-- Convert BlockQuotes (originally callout/warning environments) to admonition syntax.
-- Pandoc converts \begin{quote}...\end{quote} to BlockQuote elements.
-- We detect the content prefix to choose the admonition type:
--   **Warning:** ... -> !!! warning
--   (default)       -> !!! note
function BlockQuote(el)
    -- Build the admonition as a raw markdown block
    local content = pandoc.write(pandoc.Pandoc(el.content), "markdown")

    -- Detect admonition type from content prefix
    local admonition_type = "note"

    if content:match("^%*%*Warning:%*%*") then
        admonition_type = "warning"
        -- Strip the prefix; the admonition type already conveys it
        content = content:gsub("^%*%*Warning:%*%*%s*", "")
    end

    -- Indent all lines by 4 spaces for admonition body
    local indented = ""
    for line in content:gmatch("([^\n]*)\n?") do
        if line ~= "" then
            indented = indented .. "    " .. line .. "\n"
        else
            indented = indented .. "\n"
        end
    end

    local result = '!!! ' .. admonition_type .. ' ""\n' .. indented
    return pandoc.RawBlock("markdown", result)
end

-- Fix image paths: resolve media/ references relative to the source file.
-- EnergyPlus docs use \graphicspath{{media/}} so images are referenced by
-- filename only. We prefix them with the doc set's media directory.
function Image(el)
    local src = el.src
    -- If the path doesn't already have a directory prefix and doesn't start
    -- with http, prefix with media/
    if not src:match("^https?://") and not src:match("/") then
        el.src = "media/" .. src
    end
    return el
end

-- Handle figure environments: preserve captions as visible text and emit
-- label anchors so \ref{} cross-references can link to the figure.
-- Pandoc 3.x parses \begin{figure}...\end{figure} into a Figure AST element
-- whose caption would otherwise be lost (only stored as image alt text).
--
-- We walk the Figure's content blocks directly to extract Image elements
-- instead of re-serializing through pandoc.write(), which produces
-- implicit-figure markdown (![](src)) that clean_empty_links can corrupt.
function Figure(el)
    local lines = {}

    -- Emit an anchor for the figure's \label{} so \ref{} can link here
    local fig_id = el.identifier
    if fig_id and fig_id ~= "" then
        table.insert(lines, '<a id="' .. fig_id .. '"></a>')
        table.insert(lines, "")
    end

    -- Extract caption: plain-text for image alt attribute, markdown for
    -- the visible "*Figure: ...*" line.
    local alt_text = ""
    local caption_md = ""
    if el.caption and el.caption.long and #el.caption.long > 0 then
        alt_text = pandoc.utils.stringify(pandoc.Pandoc(el.caption.long))
        -- Strip \label{} artifacts that Pandoc leaves in captions
        -- (e.g. \protect\label{} becomes empty brackets "[]")
        alt_text = alt_text:gsub("%s*%[%]", ""):gsub("^%s+", ""):gsub("%s+$", "")

        caption_md = pandoc.write(pandoc.Pandoc(el.caption.long), "markdown")
        caption_md = caption_md:gsub("%s*%[%]", "")
        caption_md = caption_md:gsub('%s*<span id="[^"]*"></span>', "")
        caption_md = caption_md:gsub("^%s+", ""):gsub("%s+$", "")
    end

    -- Walk content blocks to find Image elements and render them directly.
    -- The Image filter has already run so src paths are correct.
    local images_rendered = false
    for _, block in ipairs(el.content) do
        if block.t == "Plain" or block.t == "Para" then
            for _, inline in ipairs(block.content) do
                if inline.t == "Image" then
                    images_rendered = true
                    table.insert(lines, "![" .. alt_text .. "](" .. inline.src .. ")")
                end
            end
        end
    end

    -- Fallback for figures without images (rare but possible)
    if not images_rendered then
        local content_doc = pandoc.Pandoc(el.content)
        local content_md = pandoc.write(content_doc, "markdown"):gsub("%s+$", "")
        table.insert(lines, content_md)
    end

    -- Add visible caption below the image
    if caption_md ~= "" then
        table.insert(lines, "")
        table.insert(lines, "*Figure: " .. caption_md .. "*")
    end

    return pandoc.RawBlock("markdown", table.concat(lines, "\n"))
end

-- Clean up Pandoc artifacts from heading attributes
function Header(el)
    -- Remove .unnumbered class that Pandoc adds for starred sections
    local new_classes = {}
    for _, cls in ipairs(el.classes) do
        if cls ~= "unnumbered" then
            table.insert(new_classes, cls)
        end
    end
    el.classes = new_classes
    return el
end

-- Fix math content: convert \textsubscript/\textsuperscript to proper math
-- notation.  Label extraction for DisplayMath is handled by the Para handler
-- so the anchor stays in the same RawBlock as the $$ math.
function Math(el)
    local text = el.text

    -- Convert \textsubscript{x} -> _{x} and \textsuperscript{x} -> ^{x}
    text = text:gsub("\\textsubscript(%b{})", function(braced)
        return "_{" .. braced:sub(2, -2) .. "}"
    end)
    text = text:gsub("\\textsuperscript(%b{})", function(braced)
        return "^{" .. braced:sub(2, -2) .. "}"
    end)

    el.text = text
    return el
end

-- Handle Pandoc-processed \ref{} and \eqref{} links.
-- Pandoc 3.x parses \ref{label} into Link elements with
-- reference-type="ref" attribute instead of leaving them as RawInline.
-- For \eqref{} references, we emit a placeholder span so the postprocessor
-- can decide same-page vs cross-page handling.
function Link(el)
    local ref_type = el.attributes["reference-type"]
    if ref_type == "eqref" then
        local label = el.attributes["reference"] or ""
        if label ~= "" then
            return pandoc.RawInline("html",
                '<span class="eqref-placeholder" data-label="' .. label .. '"></span>')
        end
    elseif ref_type == "ref" then
        local label = el.attributes["reference"] or ""
        if label ~= "" then
            el.target = "#crossref:" .. label
            -- Clean up the Pandoc attributes so they don't leak into output
            el.attributes["reference-type"] = nil
            el.attributes["reference"] = nil
            -- Clean up escaped brackets in link text: \[label\] -> label
            if #el.content == 1 and el.content[1].t == "Str" then
                local text = el.content[1].text
                text = text:gsub("^%[", ""):gsub("%]$", "")
                el.content = {pandoc.Str(text)}
            end
            return el
        end
    end
    return el
end

-- Handle RawInline LaTeX commands that Pandoc didn't process
function RawInline(el)
    if el.format == "latex" then
        -- Handle \hyperref[label]{text} cross-references
        local label, text = el.text:match("\\hyperref%[([^%]]+)%](%b{})")
        if label and text then
            -- Strip outer braces from text
            text = text:sub(2, -2)
            -- Create a link with an anchor reference (resolved in postprocessing)
            return pandoc.Link(text, "#crossref:" .. label)
        end

        -- Handle \ref{label} references
        local ref_label = el.text:match("\\ref(%b{})")
        if ref_label then
            ref_label = ref_label:sub(2, -2)
            return pandoc.Link(ref_label, "#crossref:" .. ref_label)
        end

        -- Handle \eqref{label} references (equation references with parentheses)
        -- Emit a placeholder span for the postprocessor to resolve
        local eqref_label = el.text:match("\\eqref(%b{})")
        if eqref_label then
            eqref_label = eqref_label:sub(2, -2)
            return pandoc.RawInline("html",
                '<span class="eqref-placeholder" data-label="' .. eqref_label .. '"></span>')
        end

        -- Handle \label{} outside of math environments - emit as an anchor span.
        -- Labels inside math environments are preserved by the Para and RawBlock
        -- handlers so MathJax can create numbered equation anchors.
        local lbl = el.text:match("\\label(%b{})")
        if lbl then
            lbl = lbl:sub(2, -2)
            return pandoc.RawInline("html", '<span id="' .. lbl .. '"></span>')
        end
    end
    return el
end

-- Split paragraphs that contain DisplayMath into separate blocks.
-- When Pandoc wraps display math inside a Para with surrounding text,
-- it renders as inline $<span>...$ instead of display $$ blocks.
-- This handler extracts DisplayMath into standalone RawBlock elements.
-- Labeled equations are wrapped in \begin{equation}...\end{equation}
-- so MathJax can number them via AMS auto-numbering.
function Para(el)
    -- Check if this paragraph contains any DisplayMath
    local has_display_math = false
    for _, item in ipairs(el.content) do
        if item.t == "Math" and item.mathtype == "DisplayMath" then
            has_display_math = true
            break
        end
    end

    if not has_display_math then
        return el
    end

    -- Split the paragraph content around DisplayMath elements
    local blocks = {}
    local current_inlines = {}

    for _, item in ipairs(el.content) do
        if item.t == "Math" and item.mathtype == "DisplayMath" then
            -- Flush any accumulated inline content as a Para
            if #current_inlines > 0 then
                -- Trim leading/trailing spaces
                while #current_inlines > 0 and current_inlines[1].t == "Space" do
                    table.remove(current_inlines, 1)
                end
                while #current_inlines > 0 and current_inlines[#current_inlines].t == "Space" do
                    table.remove(current_inlines)
                end
                if #current_inlines > 0 then
                    table.insert(blocks, pandoc.Para(current_inlines))
                end
                current_inlines = {}
            end

            -- Output as plain $$ display math.  MathJax tags:"all" numbers
            -- every \[...\] block (arithmatex converts $$ to \[...\]).
            -- \label{} is kept in the math so MathJax creates anchors.
            -- We do NOT wrap in \begin{equation} to avoid nesting errors
            -- with arithmatex's \[...\] wrapper.
            local math_text = item.text
            local label = math_text:match("\\label{([^}]+)}")
            local anchor = ""
            if label then
                anchor = '<span id="mjx-eqn-' .. label .. '"></span>\n\n'
            end
            table.insert(blocks, pandoc.RawBlock("markdown",
                anchor .. "$$\n" .. math_text .. "\n$$"))
        else
            table.insert(current_inlines, item)
        end
    end

    -- Flush remaining inlines
    if #current_inlines > 0 then
        while #current_inlines > 0 and current_inlines[1].t == "Space" do
            table.remove(current_inlines, 1)
        end
        while #current_inlines > 0 and current_inlines[#current_inlines].t == "Space" do
            table.remove(current_inlines)
        end
        if #current_inlines > 0 then
            table.insert(blocks, pandoc.Para(current_inlines))
        end
    end

    if #blocks == 0 then
        return {}
    elseif #blocks == 1 then
        return blocks[1]
    else
        return blocks
    end
end

-- Handle RawBlock LaTeX that Pandoc didn't process.
-- Equation environments keep their \label{} commands intact so MathJax
-- can create numbered equations and anchors via useLabelIds.
-- Align environments are preserved as-is (not converted to aligned)
-- so MathJax can number each labeled row independently.
function RawBlock(el)
    if el.format == "latex" then
        -- Handle equation environments — strip \begin{equation} wrapper to
        -- avoid nesting with arithmatex's \[...\].  MathJax tags:"all" numbers
        -- every display block.  Keep \label{} for anchors.
        local eq_content = el.text:match("\\begin{equation}(.-)\\end{equation}")
        if eq_content then
            local label = eq_content:match("\\label{([^}]+)}")
            local anchor = ""
            if label then
                anchor = '<span id="mjx-eqn-' .. label .. '"></span>\n\n'
            end
            return pandoc.RawBlock("markdown",
                anchor .. "$$\n" .. eq_content .. "\n$$")
        end

        -- Handle align/align* environments — keep as $$ blocks for MathJax.
        local align_env, align_content = el.text:match("\\begin{(align%*?)}(.-)\\end{align%*?}")
        if align_content then
            local anchors = ""
            for lbl in align_content:gmatch("\\label{([^}]+)}") do
                anchors = anchors .. '<span id="mjx-eqn-' .. lbl .. '"></span>\n'
            end
            if anchors ~= "" then anchors = anchors .. "\n" end
            return pandoc.RawBlock("markdown",
                anchors .. "$$\n\\begin{" .. align_env .. "}" .. align_content ..
                "\\end{" .. align_env .. "}\n$$")
        end
    end
    return el
end
