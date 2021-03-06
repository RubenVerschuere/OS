Blockly.Blocks['servo_init'] = {
  init: function() {
    this.appendDummyInput()
        .appendField(new Blockly.FieldImage("static/icons/fa-gears.png", 16, 18, ""))
        .appendField("Initialize servos");
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(345);
    this.setTooltip('Initialize the servo control chip.\nThis must be done before servos can be used.');
  }
};
Blockly.Lua['servo_init'] = function(block) {
  var code = 'Hardware:servo_init()\n';
  return code;
};

Blockly.Blocks['servo_enabledisable'] = {
  init: function() {
    this.appendDummyInput()
        .appendField(new Blockly.FieldImage("static/icons/fa-gears.png", 16, 18, ""))
        .appendField("Turn all servos")
        .appendField(new Blockly.FieldDropdown([["on", "ON"], ["off", "OFF"]]), "ONOFF");
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(345);
    this.setTooltip('Enables or disables all servos.');
  }
};
Blockly.Lua['servo_enabledisable'] = function(block) {
  var dropdown_onoff = block.getFieldValue('ONOFF');
  var code = '';
  if(dropdown_onoff == "ON"){
    code = "Hardware:servo_enable()\n"
  }else{
    code = "Hardware:servo_disable()\n"
  }
  return code;
};

Blockly.Blocks['servo_set'] = {
  init: function() {
    this.appendDummyInput()
        .appendField(new Blockly.FieldImage("static/icons/fa-gears.png", 16, 18, ""))
        .appendField("Set servo ")
        .appendField(new Blockly.FieldDropdown(
					[
						["0", "0"], ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"], ["5", "5"],
						["6", "6"], ["7", "7"], ["8", "8"], ["9", "9"], ["10", "10"], ["11", "11"],
						["12", "12"], ["13", "13"], ["14", "14"], ["15", "15"]
					]),
					"CHANNEL");
    this.appendValueInput("POS")
        .setCheck("Number")
        .appendField("to position");
    this.setInputsInline(true);
    this.setPreviousStatement(true);
    this.setNextStatement(true);
    this.setColour(345);
    this.setTooltip('Sets the position of one servo. Position should be between 500 and 2500.');
  }
};
Blockly.Lua['servo_set'] = function(block) {
  var dropdown_channel = block.getFieldValue('CHANNEL');
  var value_pos = Blockly.Lua.valueToCode(block, 'POS', Blockly.Lua.ORDER_ATOMIC);
  var code = 'Hardware:servo_set(' + dropdown_channel + ', ' + value_pos + ')\n';
  return code;
};
