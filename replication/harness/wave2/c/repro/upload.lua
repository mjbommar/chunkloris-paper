-- mod_lua handler: drain body, return JSON
function handle(r)
    -- requestbody(maxsize) reads the entire request body
    local body = r:requestbody(100 * 1024 * 1024)
    local n = body and #body or 0
    r.content_type = "application/json"
    r:puts(string.format('{"len":%d}', n))
    return apache2.OK
end
