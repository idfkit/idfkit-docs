-- Pandoc Lua filter for EnergyPlus documentation
--
-- Handles:
-- 1. BlockQuote -> admonition conversion (from callout environment)
-- 2. Image path resolution (media/ relative references)
-- 3. Cross-reference handling via label index
-- 4. Definition list formatting for wherelist remnants

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
