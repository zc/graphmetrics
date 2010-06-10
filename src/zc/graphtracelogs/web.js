dojo.require("dijit.form.Button");
dojo.require("dijit.Menu");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.CheckBox");

zc = function() {
    // var data = [{x: 1, y: 1}, {x: 2, y: 2}];

    // var update = function(value) {
    //     data[0] = {x: 1, y: 2};
    //     data[1] = {x: 2, y: 1};
    //     zc.chart1.updateSeries('Series 1', data);
    //     zc.chart1.render();
    // };
    var imgid = 0;

    var newChart = function(inst) {
        imgid ++;
        var div = dojo.create('div',{}, dojo.body())
        var params = {
            instance: inst,
            bust: 0
        };
        var img = dojo.create(
            'img', {id: 'img'+imgid, src: 'show.png'+qs(params)}, div);
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date == null)
                    date = '';
                else
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                params.start = date;
                params.bust++;
                img.src =  'show.png'+qs(params);
            }
        }).domNode);
        dojo.place('<span> to </span>', div)
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date == null)
                    date = '';
                else
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                params.end = date;
                params.bust++;
                img.src =  'show.png'+qs(params);
            }
        }).domNode);
        dojo.place('<span> Log:</span>', div)
        div.appendChild(new dijit.form.CheckBox({
            onChange: function(val) {
                if (val)
                    params.log = 'y';
                else
                    params.log = 'n';
                params.bust++;
                img.src =  'show.png'+qs(params);
            }
        }).domNode);
    };

    var replaceAll = function(str, orig, repl) {
        while (1) {
            var news = str.replace(orig, repl)
            if (news == str) return str;
            str = news;
        }
    };

    var qs = function(obj) {
        var delim = '?';
        var result = '';
        for (var v in obj) {
            result = result + delim + v + '=' + obj[v];
            delim = '&';
        }
        return result;
    };

    return {
        init: function()
        {
            dojo.xhrGet({
                url: 'get_instances.json',
                handleAs: 'json',
                load: function (data) {
                    var menu = new dijit.Menu({
                        style: "display: none;"
                    });
                    for (var i=0; i < data.instances.length; i++) {
                        menu.addChild(new dijit.MenuItem({
                            label: replaceAll(data.instances[i], "__", " "),
                            onClick: dojo.partial(newChart, data.instances[i])
                        }));
                    }
                    dojo.body().appendChild(new dijit.form.ComboButton({
                        label: "New chart:",
                        dropDown: menu
                    }).domNode);
                },
                error: function (error) {alert(error)}
            });


            // dojo.create('div', {id: 'simplechart',
            //                     style: "width: 250px; height: 150px;"},
            //             dojo.body())


            // var button1 = new dijit.form.Button({
            //     label: "1",
            //     onClick: function () {update(1); }});

            // dojo.body().appendChild(button1.domNode);

            // var chart1 = new dojox.charting.Chart2D("simplechart");
            // chart1.addPlot("default", {type: "Lines"});
            // chart1.addAxis("x");
            // chart1.addAxis("y", {vertical: true});
            // chart1.addSeries("Series 1", data);
            // chart1.render();
            // zc.chart1 = chart1;
        }
    }
}();

dojo.addOnLoad(zc.init);
