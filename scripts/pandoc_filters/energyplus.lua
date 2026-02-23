-- Pandoc Lua filter for EnergyPlus documentation
--
-- Handles:
-- 1. Table -> pipe-table markdown (longtable, tabular)
-- 2. CodeBlock -> fenced code blocks with language class
-- 3. BlockQuote -> admonition conversion (from callout environment)
-- 4. Image path resolution (media/ relative references)
-- 5. Cross-reference handling via label index
-- 6. Definition list formatting for wherelist remnants

-- Convert Table elements to pipe-table markdown for proper rendering.
-- Pandoc's default simple-table output wrapped in ::: divs is not supported
-- by Zensical. We serialize tables as standard pipe tables instead.
function Table(el)
    local function cell_to_text(cell)
        local doc = pandoc.Pandoc(cell.contents)
        local text = pandoc.write(doc, "markdown")
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

-- Convert BlockQuotes (originally callout environments) to admonition syntax.
-- Pandoc converts \begin{quote}...\end{quote} to BlockQuote elements.
-- We emit them as Zensical-compatible admonitions: !!! note
function BlockQuote(el)
    -- Build the admonition as a raw markdown block
    local content = pandoc.write(pandoc.Pandoc(el.content), "markdown")

    -- Indent all lines by 4 spaces for admonition body
    local indented = ""
    for line in content:gmatch("([^\n]*)\n?") do
        if line ~= "" then
            indented = indented .. "    " .. line .. "\n"
        else
            indented = indented .. "\n"
        end
    end

    local result = '!!! note ""\n' .. indented
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

        -- Handle \label{} - emit as an anchor span
        local lbl = el.text:match("\\label(%b{})")
        if lbl then
            lbl = lbl:sub(2, -2)
            return pandoc.RawInline("markdown", '<a id="' .. lbl .. '"></a>')
        end
    end
    return el
end

-- Handle RawBlock LaTeX that Pandoc didn't process
function RawBlock(el)
    if el.format == "latex" then
        -- Handle equation environments with labels
        local eq_content = el.text:match("\\begin{equation}(.-)\\end{equation}")
        if eq_content then
            -- Extract label if present
            local label = eq_content:match("\\label{([^}]+)}")
            if label then
                eq_content = eq_content:gsub("\\label{[^}]+}", "")
                return pandoc.RawBlock("markdown",
                    '<a id="' .. label .. '"></a>\n\n$$\n' ..
                    eq_content:match("^%s*(.-)%s*$") ..
                    '\n$$')
            else
                return pandoc.RawBlock("markdown",
                    "$$\n" .. eq_content:match("^%s*(.-)%s*$") .. "\n$$")
            end
        end

        -- Handle align/align* environments
        local align_content = el.text:match("\\begin{align%*?}(.-)\\end{align%*?}")
        if align_content then
            local label = align_content:match("\\label{([^}]+)}")
            if label then
                align_content = align_content:gsub("\\label{[^}]+}", "")
            end
            local prefix = label and ('<a id="' .. label .. '"></a>\n\n') or ""
            return pandoc.RawBlock("markdown",
                prefix .. "$$\n\\begin{aligned}\n" ..
                align_content:match("^%s*(.-)%s*$") ..
                "\n\\end{aligned}\n$$")
        end
    end
    return el
end
