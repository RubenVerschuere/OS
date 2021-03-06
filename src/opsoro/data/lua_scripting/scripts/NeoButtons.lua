function setup()
	-- Called once, when the script is started
	UI:init()

	UI:add_button("hello", "Hello!", "fa-hand-spock-o", false)
	UI:add_button("light", "Light!", "fa-lightbulb-o", false)

	UI:add_key("up")
	UI:add_key("down")
	UI:add_key("left")
	UI:add_key("right")

	Hardware:neo_init(8)
	Hardware:neo_set_all(0, 0, 0)
	Hardware:neo_show()
end

function loop()
	-- Called repeatedly, put your main program here
	if UI:is_key_pressed("up") then
		Hardware:neo_set_pixel(0, 75, 0, 0)
	else
		Hardware:neo_set_pixel(0, 0, 0, 0)
	end
	if UI:is_key_pressed("down") then
		Hardware:neo_set_pixel(1, 75, 75, 0)
	else
		Hardware:neo_set_pixel(1, 0, 0, 0)
	end
	if UI:is_key_pressed("left") then
		Hardware:neo_set_pixel(2, 0, 75, 0)
	else
		Hardware:neo_set_pixel(2, 0, 0, 0)
	end
	if UI:is_key_pressed("right") then
		Hardware:neo_set_pixel(3, 0, 75, 75)
	else
		Hardware:neo_set_pixel(3, 0, 0, 0)
	end
	Hardware:neo_show()
end

function quit()
	-- Called when the script is stopped
	Hardware:neo_set_all(0, 0, 0)
	Hardware:neo_show()
end
