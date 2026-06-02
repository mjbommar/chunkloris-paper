function handle(r)
    r.content_type = "application/json"
    r:puts('{"ok":true}')
    return apache2.OK
end
